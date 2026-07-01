import ipaddress
import os
import secrets
import string
from urllib.parse import urlparse

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, field_validator

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://snaplink:snaplink@localhost:5434/snaplink"
)

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
                is_active BOOLEAN NOT NULL DEFAULT true
            )
            """
        )
        conn.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')


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


@app.get("/{short_code}")
def redirect(short_code: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT target_url, is_active FROM links WHERE short_code = %s",
            (short_code,),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "not found")
    target_url, is_active = row
    if not is_active:
        raise HTTPException(410, "link disabled")
    return RedirectResponse(target_url, status_code=302)
