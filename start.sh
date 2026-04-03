#!/usr/bin/env bash
set -euo pipefail

# Render build phase usually runs without PORT.
# Runtime phase has PORT set; then we start FastAPI.
if [[ -z "${PORT:-}" ]]; then
  echo "[start.sh] Build phase detected"
  python -m pip install --upgrade pip
  python -m pip install -r backend/requirements.txt
  exit 0
fi

echo "[start.sh] Runtime phase detected. Starting API on port ${PORT}"
cd backend
exec python -m uvicorn main:app --host 0.0.0.0 --port "${PORT}"
