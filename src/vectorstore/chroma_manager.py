"""
src/vectorstore/chroma_manager.py
-----------------------------------
ChromaDB vector store manager for the Speech RAG system — Phase 3.

Handles collection creation, batch upsert, semantic search, and basic
statistics. Designed for use with a persistent on-disk ChromaDB client.

Collection schema
-----------------
- IDs       : ``chunk_id`` strings
- Embeddings: dense float32 vectors from BGE-M3 (dim=1024)
- Documents : raw chunk text
- Metadatas : flat dict (lecture_id, start_time, end_time, timestamp, …)

Usage
-----
    from src.vectorstore.chroma_manager import ChromaConfig, ChromaManager

    cfg     = ChromaConfig(db_path="vector_db", collection_name="lecture_index")
    manager = ChromaManager(cfg)

    manager.upsert(chunks, embeddings, metadatas)

    results = manager.search(query_embedding, top_k=5)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
@dataclass
class ChromaConfig:
    """
    Configuration for the ChromaDB vector store.

    Attributes
    ----------
    db_path : str
        Directory for the persistent ChromaDB client (relative to CWD
        or absolute).
    collection_name : str
        Name of the ChromaDB collection.
    distance_metric : str
        Either ``"cosine"`` (default, works with L2-normalised vectors)
        or ``"l2"``.
    upsert_batch_size : int
        Number of records sent per ChromaDB upsert call.
    """
    db_path: str = "vector_db"
    collection_name: str = "lecture_index"
    distance_metric: str = "cosine"
    upsert_batch_size: int = 128


# ──────────────────────────────────────────────────────────────
# Manager class
# ──────────────────────────────────────────────────────────────
class ChromaManager:
    """
    Manage a ChromaDB persistent vector store for lecture chunks.

    Parameters
    ----------
    config : ChromaConfig
        Database configuration.
    ephemeral : bool
        If True, use an in-memory ``EphemeralClient`` instead of a
        persistent one.  Intended for testing.
    """

    def __init__(
        self,
        config: Optional[ChromaConfig] = None,
        *,
        ephemeral: bool = False,
    ) -> None:
        self.config = config or ChromaConfig()
        self._client = None
        self._collection = None
        self._ephemeral = ephemeral
        self._connect()

    # ──────────────────────────────────────────────────────────
    # Connection
    # ──────────────────────────────────────────────────────────
    def _connect(self) -> None:
        """Open (or create) the ChromaDB client and collection."""
        try:
            import chromadb  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "chromadb is not installed. Run: pip install chromadb"
            ) from exc

        if self._ephemeral:
            self._client = chromadb.EphemeralClient()
            logger.debug("Using ephemeral (in-memory) ChromaDB client.")
        else:
            db_path = Path(self.config.db_path)
            db_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(db_path))
            logger.info("ChromaDB PersistentClient opened at '%s'.", db_path)

        self._collection = self._client.get_or_create_collection(
            name=self.config.collection_name,
            metadata={"hnsw:space": self.config.distance_metric},
        )
        logger.info(
            "Collection '%s' ready — %d vectors indexed.",
            self.config.collection_name, self._collection.count(),
        )

    # ──────────────────────────────────────────────────────────
    # Write
    # ──────────────────────────────────────────────────────────
    def upsert(
        self,
        chunks: list,
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
    ) -> int:
        """
        Insert or update chunk embeddings in the collection.

        Parameters
        ----------
        chunks : list[Chunk]
            Chunk objects; their ``chunk_id`` and ``text`` fields are used.
        embeddings : list[list[float]]
            Parallel list of embedding vectors.
        metadatas : list[dict]
            Parallel list of metadata dicts (ChromaDB-compatible scalars).

        Returns
        -------
        int
            Number of items upserted.
        """
        if not chunks:
            logger.warning("upsert: received empty chunk list. Nothing written.")
            return 0

        ids       = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        batch_sz  = self.config.upsert_batch_size
        total     = len(ids)

        logger.info("Upserting %d vectors into '%s' …", total, self.config.collection_name)
        t0 = time.perf_counter()

        for start in range(0, total, batch_sz):
            end = min(start + batch_sz, total)
            self._collection.upsert(
                ids=ids[start:end],
                embeddings=embeddings[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
            )
            logger.debug("Upserted batch [%d:%d].", start, end)

        elapsed = time.perf_counter() - t0
        logger.info(
            "Upsert complete: %d vectors in %.1fs.", total, elapsed,
        )
        return total

    # ──────────────────────────────────────────────────────────
    # Search
    # ──────────────────────────────────────────────────────────
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform approximate nearest-neighbour search.

        Parameters
        ----------
        query_embedding : list[float]
            Dense query vector from :meth:`~src.embedding.embedder.Embedder.embed_query`.
        top_k : int
            Maximum number of results to return.
        where : dict, optional
            ChromaDB metadata filter (e.g. ``{"lecture_id": "lecture_01"}``).

        Returns
        -------
        list[dict]
            Each element is a search result dict built by
            :func:`~src.retrieval.metadata_builder.build_search_result`.
            Keys: ``text``, ``lecture_id``, ``timestamp``, ``start_time``,
            ``end_time``, ``score``, ``chunk_id``.
        """
        from src.retrieval.metadata_builder import build_search_result

        n_available = self._collection.count()
        if n_available == 0:
            logger.warning("search() called on an empty collection.")
            return []

        effective_k = min(top_k, n_available)
        query_args: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results":        effective_k,
            "include":          ["documents", "metadatas", "distances"],
        }
        if where:
            query_args["where"] = where

        raw = self._collection.query(**query_args)

        results: List[Dict[str, Any]] = []
        for doc, meta, dist, doc_id in zip(
            raw["documents"][0],
            raw["metadatas"][0],
            raw["distances"][0],
            raw["ids"][0],
        ):
            results.append(build_search_result(doc, meta, dist, chunk_id=doc_id))

        logger.info("Search returned %d results (top_k=%d).", len(results), top_k)
        return results

    def search_by_text(
        self,
        query_text: str,
        embedder: Any,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Convenience method: embed *query_text* then call :meth:`search`.

        Parameters
        ----------
        query_text : str
            Student's natural-language question.
        embedder : Embedder
            A loaded :class:`~src.embedding.embedder.Embedder` instance.
        top_k : int
        where : dict, optional

        Returns
        -------
        list[dict]
        """
        query_vec = embedder.embed_query(query_text)
        return self.search(query_vec, top_k=top_k, where=where)

    # ──────────────────────────────────────────────────────────
    # Management
    # ──────────────────────────────────────────────────────────
    def count(self) -> int:
        """Return the number of indexed vectors."""
        return self._collection.count()

    def delete_collection(self) -> None:
        """
        Drop and recreate the collection (wipe all data).

        Use this before a full reindex with ``--reset``.
        """
        logger.warning(
            "Deleting collection '%s' — all %d vectors will be removed.",
            self.config.collection_name, self._collection.count(),
        )
        self._client.delete_collection(self.config.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.config.collection_name,
            metadata={"hnsw:space": self.config.distance_metric},
        )
        logger.info("Collection '%s' recreated (empty).", self.config.collection_name)

    def get_stats(self) -> Dict[str, Any]:
        """
        Return a summary of the current collection state.

        Returns
        -------
        dict
            ``collection_name``, ``num_vectors``, ``db_path``,
            ``distance_metric``.
        """
        return {
            "collection_name": self.config.collection_name,
            "num_vectors":     self._collection.count(),
            "db_path":         self.config.db_path,
            "distance_metric": self.config.distance_metric,
        }
