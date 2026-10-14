#!/bin/sh
# Startup script for Math Council API
# Railway injects $PORT automatically — do NOT hardcode it here.

set -e

echo "=== Math Council API starting ==="
echo "PORT=${PORT:-8080}"
echo "PYTHONPATH=${PYTHONPATH:-not set}"

# Run migrations — warn and continue if DB is not yet ready
alembic upgrade head && echo "Migrations applied." || echo "WARNING: alembic migration failed — continuing without migration."

echo "Starting uvicorn on 0.0.0.0:${PORT:-8080}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
