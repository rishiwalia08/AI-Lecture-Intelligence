"""
src/retrieval/reranker.py
--------------------------
Cross-encoder reranker for the Speech RAG pipeline — Phase 4.

Loads ``BAAI/bge-reranker-large`` via ``sentence_transformers.CrossEncoder``
to compute a fine-grained relevance score for every (query, chunk) pair.
The cross-encoder sees the full pair simultaneously, making it significantly
more accurate than bi-encoder similarity alone, at the cost of higher latency
(one forward pass per candidate).

Typical usage: call after hybrid search (20 candidates → 5 final results).

Usage
-----
    from src.retrieval.reranker import Reranker, RerankerConfig

    cfg      = RerankerConfig(model_name="BAAI/bge-reranker-large", top_n=5)
    reranker = Reranker(cfg)

    final = reranker.rerank(
        query      = "what is gradient descent",
        candidates = hybrid_results,   # list[dict] with "text" key
    )
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
@dataclass
class RerankerConfig:
    """
    Configuration for :class:`Reranker`.

    Attributes
    ----------
    model_name : str
        HuggingFace cross-encoder model identifier.
    top_n : int
        Number of results to return after reranking.
    batch_size : int
        Pairs scored per forward pass.
    device : str | None
        ``"cuda"``, ``"cpu"``, or ``None`` (auto-detect).
    enabled : bool
        If ``False``, reranker returns the original list unchanged
        (useful for `--no-rerank` flag).
    """
    model_name: str = "BAAI/bge-reranker-large"
    top_n:      int = 5
    batch_size: int = 32
    device: Optional[str] = None
    enabled: bool = True


# ──────────────────────────────────────────────────────────────
# Reranker
# ──────────────────────────────────────────────────────────────
class Reranker:
    """
    Cross-encoder reranker that scores (query, chunk_text) pairs.

    The model is loaded lazily on the first :meth:`rerank` call.

    Parameters
    ----------
    config : RerankerConfig, optional
        Reranker configuration.
    """

    def __init__(self, config: Optional[RerankerConfig] = None) -> None:
        self.config = config or RerankerConfig()
        self._model = None

    # ──────────────────────────────────────────────────────────
    # Lazy loader
    # ──────────────────────────────────────────────────────────
    def _ensure_model(self) -> None:
        """Load the CrossEncoder model if not already loaded."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Run: pip install sentence-transformers"
            ) from exc

        logger.info(
            "Loading reranker model '%s' (device=%s) …",
            self.config.model_name,
            self.config.device or "auto",
        )
        t0 = time.perf_counter()
        self._model = CrossEncoder(
            self.config.model_name,
            device=self.config.device,
        )
        logger.info(
            "Reranker '%s' ready in %.1fs.",
            self.config.model_name,
            time.perf_counter() - t0,
        )

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────
    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_n: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Score each (query, candidate_text) pair and return the top-n
        results sorted by descending reranker score.

        Parameters
        ----------
        query : str
            The cleaned user query.
        candidates : list[dict]
            Candidate chunks, each with at least a ``"text"`` key.
        top_n : int, optional
            Override ``config.top_n`` for this call.

        Returns
        -------
        list[dict]
            Top-n candidates (or the original list if reranker is
            disabled or candidates is empty), each with a
            ``"rerank_score"`` key added.
        """
        n = top_n or self.config.top_n

        if not candidates:
            logger.debug("Reranker: empty candidate list, returning [].")
            return []

        if not self.config.enabled:
            logger.info("Reranker disabled — returning first %d candidates.", n)
            return [
                {**c, "rerank_score": c.get("rrf_score", 0.0)}
                for c in candidates[:n]
            ]

        self._ensure_model()

        pairs = [(query, c.get("text", "")) for c in candidates]

        logger.info(
            "Reranking %d candidates (batch_size=%d) …",
            len(pairs), self.config.batch_size,
        )
        t0 = time.perf_counter()
        scores = self._model.predict(pairs, batch_size=self.config.batch_size)
        logger.info(
            "Reranking done in %.1fs.", time.perf_counter() - t0,
        )

        # Attach score and sort
        scored = [
            {**c, "rerank_score": float(s)}
            for c, s in zip(candidates, scores)
        ]
        scored.sort(key=lambda x: x["rerank_score"], reverse=True)

        top = scored[:n]
        logger.info(
            "Reranker: returned %d results (top score=%.4f).",
            len(top), top[0]["rerank_score"] if top else 0.0,
        )
        return top

    def is_loaded(self) -> bool:
        """Return True if the underlying model has been loaded."""
        return self._model is not None
