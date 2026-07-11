import base64
import hashlib
import hmac
import io
import ipaddress
import json
import os
import secrets
import string
import time
from datetime import datetime
from urllib.parse import urlparse

import geoip2.database
import geoip2.errors
import psycopg
import qrcode
import qrcode.image.svg
import redis
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, field_validator
from user_agents import parse as parse_ua

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://snaplink:snaplink@localhost:5434/snaplink"
)
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6380/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)
# static salt is fine pre-launch; move to a rotated secret if this ships past a portfolio demo
IP_HASH_SALT = os.environ.get("IP_HASH_SALT", "snaplink-dev-salt")
# dev default, must be a real rotated secret before this ships past a portfolio demo
SECRET_KEY = os.environ.get("SECRET_KEY", "snaplink-dev-secret").encode()
TOKEN_TTL_SECONDS = 7 * 24 * 3600
GEOIP_DB_PATH = os.environ.get("GEOIP_DB_PATH", "geoip/GeoLite2-Country.mmdb")
RATE_LIMIT_CREATE_PER_MIN = int(
    os.environ.get("RATE_LIMIT_CREATE_PER_MIN", "20"))
RATE_LIMIT_AUTH_PER_MIN = int(os.environ.get("RATE_LIMIT_AUTH_PER_MIN", "10"))

ALPHABET = string.ascii_letters + string.digits
CODE_LEN = 7
RESERVED = {"api", "admin", "login", "static", "docs", "openapi.json"}
BLOCKED_HOSTS = {"localhost", "0.0.0.0"}

app = FastAPI()


def get_conn():
    return psycopg.connect(DATABASE_URL, autocommit=True)


@app.on_event("startup")
def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS links (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                short_code VARCHAR(16) UNIQUE NOT NULL,
                target_url TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                is_active BOOLEAN NOT NULL DEFAULT true,
                click_count BIGINT NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
        conn.execute(
            "ALTER TABLE links ADD COLUMN IF NOT EXISTS click_count BIGINT NOT NULL DEFAULT 0")
        conn.execute(
            "ALTER TABLE links ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ")
        conn.execute(
            "ALTER TABLE links ADD COLUMN IF NOT EXISTS max_clicks INTEGER")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR UNIQUE NOT NULL,
                password_hash VARCHAR NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute(
            "ALTER TABLE links ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS click_events (
                id BIGSERIAL PRIMARY KEY,
                link_id UUID NOT NULL REFERENCES links(id),
                occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                referrer TEXT,
                device_type VARCHAR(16),
                browser VARCHAR(64),
                os VARCHAR(64),
                ip_hash VARCHAR(64)
            )
            """
        )
        conn.execute(
            "ALTER TABLE click_events ADD COLUMN IF NOT EXISTS country_code CHAR(2)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS click_events_link_id_idx ON click_events (link_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS click_daily_rollup (
                link_id UUID NOT NULL REFERENCES links(id),
                day DATE NOT NULL,
                clicks BIGINT NOT NULL DEFAULT 0,
                PRIMARY KEY (link_id, day)
            )
            """
        )


def is_safe_target(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname or ""
    if host in BLOCKED_HOSTS:
        return False
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return False
    except ValueError:
        pass  # not an IP literal, ok
    return True


def gen_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LEN))


# hand-rolled HMAC token instead of a JWT lib — same tamper-proof
# guarantee in ~15 lines, no dependency. Swap to PyJWT if you need standard
# JWT interop (mobile SDKs, API gateways) later.
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt,
                            n=16384, r=8, p=1, dklen=64)
    return salt.hex() + "$" + digest.hex()


def verify_password(password: str, stored: str) -> bool:
    salt_hex, _, digest_hex = stored.partition("$")
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(
        salt_hex), n=16384, r=8, p=1, dklen=64)
    return hmac.compare_digest(digest.hex(), digest_hex)


def make_token(user_id: str, email: str) -> str:
    payload = json.dumps(
        {"sub": user_id, "email": email, "exp": time.time() + TOKEN_TTL_SECONDS}).encode()
    sig = hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(payload).decode() + "." + sig


def verify_token(token: str) -> dict:
    try:
        payload_b64, sig = token.rsplit(".", 1)
        payload = base64.urlsafe_b64decode(payload_b64.encode())
        expected = hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("bad signature")
        data = json.loads(payload)
        if data["exp"] < time.time():
            raise ValueError("expired")
        return data
    except (ValueError, KeyError, TypeError):
        raise HTTPException(401, "invalid or expired token")


def get_current_user(authorization: str | None = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    return verify_token(authorization.removeprefix("Bearer "))


def get_current_user_optional(authorization: str | None = Header(None)) -> dict | None:
    if not authorization:
        return None
    return get_current_user(authorization)


class RegisterRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v or len(v) > 320:
            raise ValueError("invalid email")
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# fixed-window counter on redis (already a dependency) — good enough for
# abuse prevention on a portfolio app; swap for a sliding-window/token-bucket
# lib if you need smoother limiting under real traffic
def rate_limiter(bucket: str, limit_per_min: int):
    def check(request: Request) -> None:
        key = f"ratelimit:{bucket}:{client_ip(request)}"
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, 60)
        if count > limit_per_min:
            raise HTTPException(429, "too many requests, slow down")
    return check


@app.post("/api/auth/register", status_code=201, dependencies=[Depends(rate_limiter("auth", RATE_LIMIT_AUTH_PER_MIN))])
def register(body: RegisterRequest):
    with get_conn() as conn:
        try:
            row = conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
                (body.email, hash_password(body.password)),
            ).fetchone()
        except psycopg.errors.UniqueViolation:
            raise HTTPException(409, "email already registered")
        conn.commit()
        return {"token": make_token(str(row[0]), body.email), "user": {"id": row[0], "email": body.email}}


@app.post("/api/auth/login", dependencies=[Depends(rate_limiter("auth", RATE_LIMIT_AUTH_PER_MIN))])
def login(body: LoginRequest):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = %s", (
                body.email,)
        ).fetchone()
        if not row or not verify_password(body.password, row[1]):
            raise HTTPException(401, "invalid email or password")
        return {"token": make_token(str(row[0]), body.email), "user": {"id": row[0], "email": body.email}}


class CreateLinkRequest(BaseModel):
    target_url: str
    custom_slug: str | None = None
    expires_at: datetime | None = None
    max_clicks: int | None = None

    @field_validator("target_url")
    @classmethod
    def validate_target(cls, v: str) -> str:
        if not is_safe_target(v):
            raise ValueError(
                "target_url must be http(s) and not point to a private/internal address")
        return v

    @field_validator("custom_slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None and v.lower() in RESERVED:
            raise ValueError("slug is reserved")
        return v


@app.post("/api/links", status_code=201, dependencies=[Depends(rate_limiter("create_link", RATE_LIMIT_CREATE_PER_MIN))])
def create_link(body: CreateLinkRequest, request: Request, user: dict | None = Depends(get_current_user_optional)):
    user_id = user["sub"] if user else None
    params = (body.target_url, user_id, body.expires_at, body.max_clicks)
    with get_conn() as conn:
        if body.custom_slug:
            try:
                conn.execute(
                    "INSERT INTO links (short_code, target_url, user_id, expires_at, max_clicks) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (body.custom_slug, *params),
                )
            except psycopg.errors.UniqueViolation:
                raise HTTPException(409, "slug already taken")
            code = body.custom_slug
        else:
            for _ in range(5):
                code = gen_code()
                try:
                    conn.execute(
                        "INSERT INTO links (short_code, target_url, user_id, expires_at, max_clicks) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (code, *params),
                    )
                    break
                except psycopg.errors.UniqueViolation:
                    continue
            else:
                raise HTTPException(
                    500, "could not generate a unique code, retry")

    base = str(request.base_url)
    return {
        "short_code": code,
        "short_url": f"{base}{code}",
        "target_url": body.target_url,
        "qr_url": f"{base}api/links/{code}/qr",
    }


def hash_ip(ip: str) -> str:
    return hashlib.sha256(f"{IP_HASH_SALT}:{ip}".encode()).hexdigest()


try:
    _geoip_reader = geoip2.database.Reader(GEOIP_DB_PATH)
except (FileNotFoundError, ValueError):
    _geoip_reader = None


def lookup_country(ip: str) -> str | None:
    if _geoip_reader is None:
        return None
    try:
        return _geoip_reader.country(ip).country.iso_code
    except (geoip2.errors.AddressNotFoundError, ValueError):
        return None


def record_click(link_id: str, referrer: str | None, ua_string: str, ip: str) -> None:
    ua = parse_ua(ua_string)
    device_type = (
        "bot" if ua.is_bot else
        "mobile" if ua.is_mobile else
        "tablet" if ua.is_tablet else
        "desktop"
    )
    country_code = lookup_country(ip)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO click_events (link_id, referrer, device_type, browser, os, ip_hash, country_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (link_id, referrer, device_type,
             ua.browser.family, ua.os.family, hash_ip(ip), country_code),
        )
        conn.execute(
            "UPDATE links SET click_count = click_count + 1 WHERE id = %s", (
                link_id,)
        )
        conn.execute(
            """
            INSERT INTO click_daily_rollup (link_id, day, clicks)
            VALUES (%s, current_date, 1)
            ON CONFLICT (link_id, day) DO UPDATE SET clicks = click_daily_rollup.clicks + 1
            """,
            (link_id,),
        )


RANGE_INTERVALS = {"24h": "1 day",
                   "7d": "7 days", "30d": "30 days", "all": None}


@app.get("/api/links")
def list_links(user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT short_code, target_url, click_count, created_at, is_active "
            "FROM links WHERE user_id = %s ORDER BY created_at DESC",
            (user["sub"],),
        ).fetchall()
    return [
        {
            "short_code": r[0],
            "target_url": r[1],
            "click_count": r[2],
            "created_at": r[3],
            "is_active": r[4],
        }
        for r in rows
    ]


@app.get("/api/links/{short_code}")
def get_link(short_code: str, user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT short_code, target_url, click_count, created_at, is_active, "
            "expires_at, max_clicks, user_id FROM links WHERE short_code = %s",
            (short_code,),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "not found")
    if row[7] is None or str(row[7]) != user["sub"]:
        raise HTTPException(403, "not your link")
    return {
        "short_code": row[0],
        "target_url": row[1],
        "click_count": row[2],
        "created_at": row[3],
        "is_active": row[4],
        "expires_at": row[5],
        "max_clicks": row[6],
    }


class UpdateLinkRequest(BaseModel):
    is_active: bool | None = None
    expires_at: datetime | None = None


def _owned_link_id(conn, short_code: str, user_sub: str) -> str:
    row = conn.execute(
        "SELECT id, user_id FROM links WHERE short_code = %s", (short_code,)).fetchone()
    if row is None:
        raise HTTPException(404, "not found")
    link_id, owner_id = row
    if owner_id is None or str(owner_id) != user_sub:
        raise HTTPException(403, "not your link")
    return link_id


@app.patch("/api/links/{short_code}")
def update_link(short_code: str, body: UpdateLinkRequest, user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        _owned_link_id(conn, short_code, user["sub"])
        fields = body.model_dump(exclude_unset=True)
        if fields:
            set_clause = ", ".join(f"{k} = %s" for k in fields)
            conn.execute(
                f"UPDATE links SET {set_clause} WHERE short_code = %s",
                (*fields.values(), short_code),
            )
    # redirect cache has no TTL (see redirect()) — must DEL on every write
    redis_client.delete(_cache_key(short_code))
    return {"short_code": short_code, "updated": True}


@app.delete("/api/links/{short_code}", status_code=204)
def delete_link(short_code: str, user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        link_id = _owned_link_id(conn, short_code, user["sub"])
        conn.execute(
            "DELETE FROM click_daily_rollup WHERE link_id = %s", (link_id,))
        conn.execute("DELETE FROM click_events WHERE link_id = %s", (link_id,))
        conn.execute("DELETE FROM links WHERE id = %s", (link_id,))
    redis_client.delete(_cache_key(short_code))
    redis_client.delete(f"clicks:{short_code}")


@app.get("/api/links/{short_code}/analytics")
def link_analytics(short_code: str, range: str = "7d", user: dict = Depends(get_current_user)):
    if range not in RANGE_INTERVALS:
        raise HTTPException(
            400, f"range must be one of {list(RANGE_INTERVALS)}")
    interval = RANGE_INTERVALS[range]
    since_clause = f"AND occurred_at >= now() - interval '{interval}'" if interval else ""
    # string-built interval clause is safe here — `interval` only ever comes
    # from RANGE_INTERVALS' fixed values above, never from the request directly

    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, user_id FROM links WHERE short_code = %s", (short_code,)).fetchone()
        if row is None:
            raise HTTPException(404, "not found")
        link_id, owner_id = row
        if owner_id is not None and str(owner_id) != user["sub"]:
            raise HTTPException(403, "not your link")

        total_clicks, unique_visitors = conn.execute(
            f"""
            SELECT count(*), count(DISTINCT ip_hash)
            FROM click_events WHERE link_id = %s {since_clause}
            """,
            (link_id,),
        ).fetchone()

        rollup_since = f"AND day >= (now() - interval '{interval}')::date" if interval else ""
        series = conn.execute(
            f"""
            SELECT day, clicks
            FROM click_daily_rollup WHERE link_id = %s {rollup_since}
            ORDER BY day
            """,
            (link_id,),
        ).fetchall()

        referrers = conn.execute(
            f"""
            SELECT coalesce(referrer, 'Direct'), count(*)
            FROM click_events WHERE link_id = %s {since_clause}
            GROUP BY 1 ORDER BY 2 DESC LIMIT 8
            """,
            (link_id,),
        ).fetchall()

        devices = conn.execute(
            f"""
            SELECT device_type, count(*)
            FROM click_events WHERE link_id = %s {since_clause}
            GROUP BY 1 ORDER BY 2 DESC
            """,
            (link_id,),
        ).fetchall()

        browsers = conn.execute(
            f"""
            SELECT browser, count(*)
            FROM click_events WHERE link_id = %s {since_clause}
            GROUP BY 1 ORDER BY 2 DESC LIMIT 6
            """,
            (link_id,),
        ).fetchall()

        countries = conn.execute(
            f"""
            SELECT coalesce(country_code, 'Unknown'), count(*)
            FROM click_events WHERE link_id = %s {since_clause}
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10
            """,
            (link_id,),
        ).fetchall()

    peak_day = max(series, key=lambda r: r[1])[0] if series else None

    return {
        "total_clicks": total_clicks,
        "unique_visitors": unique_visitors,
        "peak_day": peak_day,
        "series": [{"date": str(d), "clicks": c} for d, c in series],
        "referrers": [{"referrer": r, "clicks": c} for r, c in referrers],
        "devices": [{"device_type": d, "clicks": c} for d, c in devices],
        "browsers": [{"browser": b, "clicks": c} for b, c in browsers],
        "countries": [{"country_code": cc, "clicks": c} for cc, c in countries],
    }


@app.get("/api/links/{short_code}/qr")
def link_qr(short_code: str, request: Request):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM links WHERE short_code = %s", (short_code,)).fetchone()
    if row is None:
        raise HTTPException(404, "not found")
    img = qrcode.make(f"{request.base_url}{short_code}",
                      image_factory=qrcode.image.svg.SvgImage)
    buf = io.BytesIO()
    img.save(buf)
    return Response(buf.getvalue(), media_type="image/svg+xml")


def _cache_key(short_code: str) -> str:
    return f"link:{short_code}"


@app.get("/{short_code}")
def redirect(short_code: str, request: Request, background_tasks: BackgroundTasks):
    cached = redis_client.get(_cache_key(short_code))
    if cached is not None:
        link = json.loads(cached)
    else:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT id, target_url, is_active, expires_at, max_clicks, click_count "
                "FROM links WHERE short_code = %s",
                (short_code,),
            ).fetchone()
        if row is None:
            raise HTTPException(404, "not found")
        link_id, target_url, is_active, expires_at, max_clicks, click_count = row
        link = {
            "id": str(link_id),
            "target_url": target_url,
            "is_active": is_active,
            "expires_at": expires_at.isoformat() if expires_at else None,
            "max_clicks": max_clicks,
        }
        # cached without a TTL: is_active/expires_at/max_clicks are set at creation
        # and never mutated elsewhere today. A future PATCH/DELETE endpoint must
        # DEL this key on write.
        redis_client.set(_cache_key(short_code), json.dumps(link))
        if max_clicks is not None:
            redis_client.set(f"clicks:{short_code}", click_count, nx=True)

    if not link["is_active"]:
        raise HTTPException(410, "link disabled")
    expires_at = datetime.fromisoformat(
        link["expires_at"]) if link["expires_at"] else None
    if expires_at and expires_at < datetime.now(expires_at.tzinfo):
        raise HTTPException(410, "link expired")
    if link["max_clicks"] is not None:
        count = redis_client.incr(f"clicks:{short_code}")
        if count > link["max_clicks"]:
            raise HTTPException(410, "link reached max clicks")

    background_tasks.add_task(
        record_click,
        link["id"],
        request.headers.get("referer"),
        request.headers.get("user-agent", ""),
        client_ip(request),
    )
    return RedirectResponse(link["target_url"], status_code=302)
