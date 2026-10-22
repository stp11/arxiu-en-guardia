#!/bin/sh
set -e

echo "Starting application on port $PORT"

echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete."

# Start uvicorn with proxy headers enabled
# --forwarded-allow-ips="*" trusts X-Forwarded-Proto from Cloudflare for HTTPS detection
echo "Starting uvicorn..."
exec uvicorn main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8080} --forwarded-allow-ips="*"
