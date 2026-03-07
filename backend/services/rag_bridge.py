"""
backend/services/rag_bridge.py
---------------------------------
Thread-safe lazy singleton wrapper around ``src.services.rag_service.RAGService``.

The RAGService loads heavy models (BGE-M3 embedder, ChromaDB client, optionally
the cross-encoder reranker).  We initialise it exactly once at server startup
via the FastAPI lifespan handler and then reuse it across all requests.

Usage
-----
    from backend.services.rag_bridge import get_rag_bridge, RAGBridge

    bridge = get_rag_bridge()          # returns singleton
    result = bridge.ask("What is KMP?")
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Make project root importable
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.services.rag_service import RAGService, RAGServiceConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)

_lock:     threading.Lock = threading.Lock()
_instance: Optional["RAGBridge"] = None


class RAGBridge:
    """
    Thin wrapper around :class:`~src.services.rag_service.RAGService`.

    Provides a simplified ``ask()`` interface for the API layer and
    tracks whether the service has been successfully initialised.
    """

    def __init__(self, config_path: str | Path | None = None) -> None:
        self._ready    = False
        self._error:   Optional[str] = None
        self._svc:     Optional[RAGService] = None
        self._cfg_path = config_path or (_PROJECT_ROOT / "config" / "config.yaml")

    def initialise(self) -> None:
        """Load the RAGService and build the BM25 index. Called once at startup."""
        logger.info("RAGBridge: initialising RAGService from '%s'.", self._cfg_path)
        t0 = time.perf_counter()
        try:
            cfg        = RAGServiceConfig.from_yaml(self._cfg_path, project_root=_PROJECT_ROOT)
            self._svc  = RAGService(cfg)
            self._svc._retrieval.build_bm25_index()
            self._ready = True
            logger.info("RAGBridge: ready in %.1fs.", time.perf_counter() - t0)
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            logger.error("RAGBridge: initialisation failed: %s", exc)

    def ask(
        self,
        query:          str,
        input_type:     str = "text",
        top_n:          int = 5,
        lecture_filter: Optional[str] = None,
        provider:       Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run the full RAG pipeline for a text or audio query.

        Parameters
        ----------
        query : str
        input_type : "text" | "audio"
        top_n : int
        lecture_filter : str, optional
        provider : str, optional   Ignored — provider set at init time via config.

        Returns
        -------
        dict  Keys: ``"answer"``, ``"sources"``
        """
        if not self._ready or self._svc is None:
            raise RuntimeError(
                f"RAGService not ready. Init error: {self._error or 'unknown'}"
            )

        return self._svc.ask_question(
            query=query,
            input_type=input_type,
            top_n=top_n,
            lecture_filter=lecture_filter,
        )

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def error(self) -> Optional[str]:
        return self._error


def get_rag_bridge(config_path: str | Path | None = None) -> RAGBridge:
    """
    Return (or create) the global :class:`RAGBridge` singleton.

    Thread-safe — safe to call from multiple async workers simultaneously.
    """
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = RAGBridge(config_path)
    return _instance


def reset_rag_bridge() -> None:
    """Reset the singleton — used in tests."""
    global _instance
    with _lock:
        _instance = None
