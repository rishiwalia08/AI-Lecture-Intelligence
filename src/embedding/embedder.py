"""
src/embedding/embedder.py
--------------------------
Embedding generation module for the Speech RAG system — Phase 3.

Wraps the BAAI/bge-m3 model via ``sentence-transformers`` for both
document and query embedding with configurable batch processing.

BGE-M3 is a multilingual, multi-granularity retrieval model that
produces dense 1024-d embeddings and supports both retrieval and
re-ranking. The sentence-transformers wrapper handles the instruction
prefix automatically.

Usage
-----
    from src.embedding.embedder import EmbedderConfig, Embedder

    config  = EmbedderConfig(model_name="BAAI/bge-m3", batch_size=32)
    embedder = Embedder(config)

    # Single query
    vec = embedder.embed_query("What is the KMP algorithm?")

    # Batch chunks
    from src.embedding.chunking import Chunk
    vectors = embedder.embed_chunks(chunks)   # list[list[float]]
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
@dataclass
class EmbedderConfig:
    """
    Configuration for the embedding model.

    Attributes
    ----------
    model_name : str
        HuggingFace model identifier (default ``"BAAI/bge-m3"``).
    batch_size : int
        Number of texts encoded per forward pass.
    device : str | None
        ``"cuda"``, ``"cpu"``, or ``None`` (auto-detect).
    normalize_embeddings : bool
        L2-normalise output vectors (required for cosine similarity
        with ChromaDB's ``cosine`` metric).
    show_progress_bar : bool
        Display tqdm bar during batch encoding.
    """
    model_name: str = "BAAI/bge-m3"
    batch_size: int = 32
    device: Optional[str] = None           # None = auto
    normalize_embeddings: bool = True
    show_progress_bar: bool = True


# ──────────────────────────────────────────────────────────────
# Embedder class
# ──────────────────────────────────────────────────────────────
class Embedder:
    """
    Wraps a sentence-transformers model for document and query embedding.

    The model is loaded lazily on the first call to
    :meth:`_ensure_model` to avoid import-time overhead.

    Parameters
    ----------
    config : EmbedderConfig
        Embedding configuration.
    """

    def __init__(self, config: Optional[EmbedderConfig] = None) -> None:
        self.config = config or EmbedderConfig()
        self._model = None   # lazy-loaded

    # ──────────────────────────────────────────────────────────
    # Lazy model loader
    # ──────────────────────────────────────────────────────────
    def _ensure_model(self) -> None:
        """Load the SentenceTransformer model if not already loaded."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Run: pip install sentence-transformers"
            ) from exc

        logger.info(
            "Loading embedding model '%s' (device=%s) …",
            self.config.model_name,
            self.config.device or "auto",
        )
        t0 = time.perf_counter()
        self._model = SentenceTransformer(
            self.config.model_name,
            device=self.config.device,
        )
        logger.info(
            "Model '%s' ready in %.1fs.", self.config.model_name,
            time.perf_counter() - t0,
        )

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────
    def generate_embedding(self, text: str) -> List[float]:
        """
        Embed a single document text.

        Parameters
        ----------
        text : str
            Raw chunk text.

        Returns
        -------
        list[float]
            Dense embedding vector.
        """
        self._ensure_model()
        vector = self._model.encode(
            text,
            normalize_embeddings=self.config.normalize_embeddings,
            show_progress_bar=False,
        )
        return vector.tolist()

    def embed_chunks(self, chunks: list) -> List[List[float]]:
        """
        Generate embeddings for a list of :class:`~src.embedding.chunking.Chunk`
        objects in batches.

        Parameters
        ----------
        chunks : list[Chunk]
            Chunks from :func:`~src.embedding.chunking.create_chunks`.

        Returns
        -------
        list[list[float]]
            One embedding vector per chunk, in the same order.
        """
        if not chunks:
            return []

        self._ensure_model()
        texts = [c.text for c in chunks]
        logger.info(
            "Embedding %d chunks (batch_size=%d) …",
            len(texts), self.config.batch_size,
        )
        t0 = time.perf_counter()

        vectors = self._model.encode(
            texts,
            batch_size=self.config.batch_size,
            normalize_embeddings=self.config.normalize_embeddings,
            show_progress_bar=self.config.show_progress_bar,
        )
        elapsed = time.perf_counter() - t0
        logger.info(
            "Embedded %d chunks in %.1fs (%.0f chunks/s).",
            len(texts), elapsed, len(texts) / elapsed if elapsed > 0 else 0,
        )
        return [v.tolist() for v in vectors]

    def embed_query(self, query_text: str) -> List[float]:
        """
        Embed a user query for retrieval.

        BGE-M3 performs optimally when the query is passed without any
        special prefix via ``sentence_transformers`` (the library applies
        the correct prompt internally when the model is loaded from HF).

        Parameters
        ----------
        query_text : str
            The student's question or search string.

        Returns
        -------
        list[float]
            Dense query embedding vector.
        """
        self._ensure_model()
        vector = self._model.encode(
            query_text,
            normalize_embeddings=self.config.normalize_embeddings,
            show_progress_bar=False,
        )
        return vector.tolist()

    @property
    def embedding_dim(self) -> Optional[int]:
        """
        Return the embedding dimensionality, or ``None`` if the model
        is not yet loaded.
        """
        if self._model is None:
            return None
        return self._model.get_sentence_embedding_dimension()
