#!/usr/bin/env bash
# Production entrypoint: apply migrations, then serve with gunicorn + uvicorn workers.
set -euo pipefail
echo "Running database migrations…"
alembic upgrade head
echo "Starting Lexa…"
exec gunicorn app.main:app \
  -k uvicorn.workers.UvicornWorker \
  -b "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 120 \
  --access-logfile - --error-logfile -
