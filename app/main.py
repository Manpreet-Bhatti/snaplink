import hashlib
import ipaddress
import os
import secrets
import string
from urllib.parse import urlparse

import psycopg
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, field_validator
from user_agents import parse as parse_ua

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://snaplink:snaplink@localhost:5434/snaplink"
)
# ponytail: static salt is fine pre-launch; move to a rotated secret if this ships past a portfolio demo
IP_HASH_SALT = os.environ.get("IP_HASH_SALT", "snaplink-dev-salt")

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
            "CREATE INDEX IF NOT EXISTS click_events_link_id_idx ON click_events (link_id)"
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


class CreateLinkRequest(BaseModel):
    target_url: str
    custom_slug: str | None = None

    @field_validator("target_url")
    @classmethod
    def validate_target(cls, v: str) -> str:
        if not is_safe_target(v):
            raise ValueError("target_url must be http(s) and not point to a private/internal address")
        return v

    @field_validator("custom_slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None and v.lower() in RESERVED:
            raise ValueError("slug is reserved")
        return v


@app.post("/api/links", status_code=201)
def create_link(body: CreateLinkRequest):
    with get_conn() as conn:
        if body.custom_slug:
            try:
                conn.execute(
                    "INSERT INTO links (short_code, target_url) VALUES (%s, %s)",
                    (body.custom_slug, body.target_url),
                )
            except psycopg.errors.UniqueViolation:
                raise HTTPException(409, "slug already taken")
            code = body.custom_slug
        else:
            for _ in range(5):
                code = gen_code()
                try:
                    conn.execute(
                        "INSERT INTO links (short_code, target_url) VALUES (%s, %s)",
                        (code, body.target_url),
                    )
                    break
                except psycopg.errors.UniqueViolation:
                    continue
            else:
                raise HTTPException(500, "could not generate a unique code, retry")

    return {
        "short_code": code,
        "short_url": f"/{code}",
        "target_url": body.target_url,
    }


def hash_ip(ip: str) -> str:
    return hashlib.sha256(f"{IP_HASH_SALT}:{ip}".encode()).hexdigest()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def record_click(link_id: str, referrer: str | None, ua_string: str, ip: str) -> None:
    ua = parse_ua(ua_string)
    device_type = (
        "bot" if ua.is_bot else
        "mobile" if ua.is_mobile else
        "tablet" if ua.is_tablet else
        "desktop"
    )
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO click_events (link_id, referrer, device_type, browser, os, ip_hash)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (link_id, referrer, device_type, ua.browser.family, ua.os.family, hash_ip(ip)),
        )
        conn.execute(
            "UPDATE links SET click_count = click_count + 1 WHERE id = %s", (link_id,)
        )


@app.get("/{short_code}")
def redirect(short_code: str, request: Request, background_tasks: BackgroundTasks):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, target_url, is_active FROM links WHERE short_code = %s",
            (short_code,),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "not found")
    link_id, target_url, is_active = row
    if not is_active:
        raise HTTPException(410, "link disabled")
    background_tasks.add_task(
        record_click,
        link_id,
        request.headers.get("referer"),
        request.headers.get("user-agent", ""),
        client_ip(request),
    )
    return RedirectResponse(target_url, status_code=302)
