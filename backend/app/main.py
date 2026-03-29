"""
backend/app/main.py
---------------------
FastAPI application entry point for the Interactive Lecture Intelligence API.

Start the server
-----------------
    # From project root:
    uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

    # Or via the helper script:
    python -m backend.app.main
"""

from __future__ import annotations

import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from backend.app.routes import router
from backend.services.rag_bridge import get_rag_bridge
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────
# Lifespan — startup / shutdown
# ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Kick off RAG initialisation without blocking server startup."""
    logger.info("🚀 Starting Interactive Lecture Intelligence API…")
    bridge = get_rag_bridge()

    def _initialise_rag() -> None:
        bridge.initialise()  # heavy load in background
        if bridge.ready:
            logger.info("✅ RAG pipeline ready.")
        else:
            logger.error("❌ RAG pipeline failed to initialise: %s", bridge.error)

    threading.Thread(target=_initialise_rag, daemon=True).start()
    logger.info("RAG pipeline initialisation started in background.")

    yield
    logger.info("🛑 Shutting down API.")


# ──────────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Interactive Lecture Intelligence API",
    description=(
        "Speech-RAG system that retrieves and answers lecture questions "
        "using hybrid semantic + BM25 search, BGE reranking, and an LLM."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────
# Allow all origins in development.  Restrict in production:
#   allow_origins=["https://yourdomain.com"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────
app.include_router(router)


# ── Frontend (single-service mode) ───────────────────────────
_FRONTEND_DIST = _PROJECT_ROOT / "frontend" / "dist"
_FRONTEND_ASSETS = _FRONTEND_DIST / "assets"

if _FRONTEND_DIST.exists():
    if _FRONTEND_ASSETS.exists():
        app.mount("/assets", StaticFiles(directory=str(_FRONTEND_ASSETS)), name="assets")

    @app.get("/", include_in_schema=False)
    async def root():
        return FileResponse(_FRONTEND_DIST / "index.html")

    @app.head("/", include_in_schema=False)
    async def root_head():
        return JSONResponse(status_code=200, content={})

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND_DIST / "index.html")

else:
    # ── Root fallback (API-only mode) ─────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root():
        return JSONResponse({"message": "Interactive Lecture Intelligence API — see /docs"})

    @app.head("/", include_in_schema=False)
    async def root_head():
        return JSONResponse(status_code=200, content={})


# ── Dev runner ────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
