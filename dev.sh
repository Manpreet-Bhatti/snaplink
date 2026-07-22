#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

docker compose up -d --wait db redis

exec uvicorn app.main:app --reload
