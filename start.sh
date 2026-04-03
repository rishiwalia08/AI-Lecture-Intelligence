#!/usr/bin/env bash
set -euo pipefail

PY_BIN="$(command -v python || true)"
if [[ -z "${PY_BIN}" ]]; then
  PY_BIN="$(command -v python3 || true)"
fi
if [[ -z "${PY_BIN}" ]]; then
  echo "[start.sh] ERROR: python interpreter not found"
  exit 127
fi

# Render build phase usually runs without PORT.
# Runtime phase has PORT set; then we start FastAPI.
if [[ -z "${PORT:-}" ]]; then
  echo "[start.sh] Build phase detected"
  "${PY_BIN}" -m pip install --upgrade pip
  "${PY_BIN}" -m pip install -r backend/requirements.txt
  exit 0
fi

echo "[start.sh] Runtime phase detected. Starting API on port ${PORT}"
cd backend
exec "${PY_BIN}" -m uvicorn main:app --host 0.0.0.0 --port "${PORT}" --loop asyncio --http h11
