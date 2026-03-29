#!/usr/bin/env bash
set -euo pipefail

PORT_VALUE="${PORT:-10000}"
echo "Starting API on 0.0.0.0:${PORT_VALUE}"
exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT_VALUE}"
