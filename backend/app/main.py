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
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    """Initialise the RAG pipeline once on server startup."""
    logger.info("🚀 Starting Interactive Lecture Intelligence API…")
    bridge = get_rag_bridge()
    bridge.initialise()          # blocks until RAGService + BM25 index ready
    if bridge.ready:
        logger.info("✅ RAG pipeline ready.")
    else:
        logger.error("❌ RAG pipeline failed to initialise: %s", bridge.error)
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


# ── Root redirect ─────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse({"message": "Interactive Lecture Intelligence API — see /docs"})


# ── Dev runner ────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
