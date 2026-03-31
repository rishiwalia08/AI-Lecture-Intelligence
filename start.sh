#!/usr/bin/env bash
set -e

# Render assigns a dynamic PORT via environment variable
# If not set, fallback to 8000 (standard web service port)
PORT_VALUE="${PORT:-8000}"

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Starting Uvicorn on 0.0.0.0:${PORT_VALUE}"
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Environment - PORT=${PORT:-not set}"

# Start Uvicorn with proper signal handling
exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT_VALUE}" --log-level info
