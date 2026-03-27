"""
src/retrieval/hybrid_search.py
---------------------------------
Hybrid semantic + BM25 keyword search for the Speech RAG pipeline — Phase 4.

Architecture
------------
                    ┌─────────────┐
  query_text  ──▶  │  BM25Index  │  ──▶  top-K BM25 results
                    └─────────────┘           │
                                              ▼
  query_embed ──▶  ChromaDB.search()  ──▶  top-K semantic results
                                              │
                                              ▼
                          ┌───────────────────────────────┐
                          │  Reciprocal Rank Fusion (RRF)  │
                          │  score = Σ 1 / (rank + k=60)   │
                          └───────────────────────────────┘
                                              │
                                              ▼
                                    top-20 merged candidates

BM25 uses the same tokenisation as :class:`~src.retrieval.query_processor.QueryProcessor`
so query and corpus representations are consistent.

Usage
-----
    from src.retrieval.hybrid_search import HybridSearcher

    searcher = HybridSearcher(chroma_manager=manager, embedder=embedder)
    searcher.build_bm25_index(all_chunks)

    results = searcher.hybrid_search(
        query_text="KMP pattern matching",
        query_embedding=embedder.embed_query("KMP pattern matching"),
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# BM25 Index
# ──────────────────────────────────────────────────────────────
class BM25Index:
    """
    Thin wrapper around ``rank_bm25.BM25Okapi`` for transcript chunks.

    Parameters
    ----------
    tokenizer : callable, optional
        Function ``str → list[str]``. Defaults to whitespace split.
    """

    def __init__(self, tokenizer=None) -> None:
        self._tokenizer = tokenizer or (lambda t: t.lower().split())
        self._bm25     = None
        self._chunks: List[Dict[str, Any]] = []

    def build(self, chunks: List[Any]) -> None:
        """
        Build the BM25 index from a list of :class:`~src.embedding.chunking.Chunk`
        objects (or any objects with ``chunk_id``, ``text``, ``lecture_id``,
        ``start_time``, ``end_time`` attributes / keys).

        Parameters
        ----------
        chunks : list
            Chunk objects from :func:`~src.embedding.chunking.create_chunks`
            **or** dicts with the same fields.
        """
        try:
            from rank_bm25 import BM25Okapi  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "rank-bm25 is not installed. Run: pip install rank-bm25"
            ) from exc

        self._chunks = []
        tokenized:   List[List[str]] = []

        for c in chunks:
            if hasattr(c, "text"):
                d = {
                    "chunk_id":   c.chunk_id,
                    "text":       c.text,
                    "lecture_id": c.lecture_id,
                    "start_time": c.start_time,
                    "end_time":   c.end_time,
                }
            else:
                d = dict(c)
            tokens = self._tokenizer(d["text"])
            # Skip empty documents — BM25 can fail when average document
            # length is zero across the corpus.
            if not tokens:
                continue

            self._chunks.append(d)
            tokenized.append(tokens)

        if not tokenized:
            self._bm25 = None
            logger.warning(
                "BM25 index not built: no non-empty chunks available. "
                "Run indexing first (Phase 3) to enable retrieval."
            )
            return

        self._bm25 = BM25Okapi(tokenized)
        logger.info("BM25 index built: %d documents.", len(self._chunks))

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Return top-k chunks ranked by BM25 score.

        Parameters
        ----------
        query : str
            Pre-processed query string.
        top_k : int

        Returns
        -------
        list[dict]
            Each dict has ``chunk_id``, ``text``, ``lecture_id``,
            ``start_time``, ``end_time``, ``bm25_score``.
        """
        if self._bm25 is None:
            logger.warning("BM25 index not built — call build() first.")
            return []

        tokens = self._tokenizer(query)
        scores = self._bm25.get_scores(tokens)

        # Pair score with chunk, sort descending
        ranked = sorted(
            zip(scores, self._chunks), key=lambda x: x[0], reverse=True
        )[:top_k]

        results = []
        for score, chunk in ranked:
            if score <= 0:
                continue
            results.append({**chunk, "bm25_score": float(score)})

        logger.debug("BM25 search returned %d results for '%s'.", len(results), query)
        return results

    @property
    def size(self) -> int:
        """Number of indexed documents."""
        return len(self._chunks)


# ──────────────────────────────────────────────────────────────
# RRF merge helper
# ──────────────────────────────────────────────────────────────
def _reciprocal_rank_fusion(
    ranked_lists: List[List[Dict[str, Any]]],
    id_key: str = "chunk_id",
    k: int = 60,
) -> List[Dict[str, Any]]:
    """
    Merge multiple ranked result lists using Reciprocal Rank Fusion.

    RRF score for document d = Σ  1 / (rank(d, list) + k)

    Parameters
    ----------
    ranked_lists : list[list[dict]]
        Each sub-list is a ranked result list (index 0 = best).
    id_key : str
        Field used to deduplicate across lists.
    k : int
        RRF smoothing constant (Cormack et al. 2009 recommend 60).

    Returns
    -------
    list[dict]
        Merged, deduplicated list sorted by descending RRF score.
        Each item gets an additional ``rrf_score`` key.
    """
    scores:   Dict[str, float] = {}
    registry: Dict[str, Dict[str, Any]] = {}

    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked):
            doc_id = doc.get(id_key, "")
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rank + 1 + k)
            if doc_id not in registry:
                registry[doc_id] = doc

    merged = []
    for doc_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        entry = {**registry[doc_id], "rrf_score": round(score, 6)}
        merged.append(entry)

    return merged


# ──────────────────────────────────────────────────────────────
# HybridSearcher
# ──────────────────────────────────────────────────────────────
@dataclass
class HybridConfig:
    """
    Configuration for :class:`HybridSearcher`.

    Attributes
    ----------
    semantic_top_k : int
        Results to retrieve from ChromaDB vector search.
    bm25_top_k : int
        Results to retrieve from BM25 keyword search.
    rrf_k : int
        RRF constant (default 60).
    max_candidates : int
        Maximum results returned after RRF merge.
    """
    semantic_top_k: int = 10
    bm25_top_k:     int = 10
    rrf_k:          int = 60
    max_candidates: int = 20


class HybridSearcher:
    """
    Combines ChromaDB semantic search and BM25 keyword search via RRF.

    Parameters
    ----------
    chroma_manager : ChromaManager
        An initialised Phase 3 :class:`~src.vectorstore.chroma_manager.ChromaManager`.
    embedder : Embedder
        A loaded Phase 3 :class:`~src.embedding.embedder.Embedder`.
    config : HybridConfig, optional
    """

    def __init__(
        self,
        chroma_manager: Any,
        embedder: Any,
        config: Optional[HybridConfig] = None,
    ) -> None:
        self.manager  = chroma_manager
        self.embedder = embedder
        self.config   = config or HybridConfig()
        self.bm25     = BM25Index(
            tokenizer=lambda t: t.lower().split()
        )

    def build_bm25_index(self, chunks: List[Any]) -> None:
        """Build (or rebuild) the in-memory BM25 index from chunk objects."""
        self.bm25.build(chunks)

    # ──────────────────────────────────────────────────────────
    # Individual search methods
    # ──────────────────────────────────────────────────────────
    def semantic_search(
        self,
        query_embedding: List[float],
        top_k: Optional[int] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic nearest-neighbour search via ChromaDB.

        Parameters
        ----------
        query_embedding : list[float]
        top_k : int, optional   Defaults to ``config.semantic_top_k``.
        where : dict, optional  ChromaDB metadata filter.

        Returns
        -------
        list[dict]
            Results from :meth:`~src.vectorstore.chroma_manager.ChromaManager.search`.
        """
        k = top_k or self.config.semantic_top_k
        results = self.manager.search(query_embedding, top_k=k, where=where)
        # Ensure chunk_id key exists (ChromaDB returns it as "chunk_id")
        return [self._normalise_semantic(r) for r in results]

    def keyword_search(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        BM25 keyword search.

        Parameters
        ----------
        query : str
            Cleaned query text.
        top_k : int, optional   Defaults to ``config.bm25_top_k``.

        Returns
        -------
        list[dict]
        """
        k = top_k or self.config.bm25_top_k
        return self.bm25.search(query, top_k=k)

    # ──────────────────────────────────────────────────────────
    # Hybrid merge
    # ──────────────────────────────────────────────────────────
    def hybrid_search(
        self,
        query_text: str,
        query_embedding: Optional[List[float]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search: semantic + BM25, merged via RRF.

        Parameters
        ----------
        query_text : str
            Cleaned query string (used for BM25 and optionally for embedding).
        query_embedding : list[float], optional
            Pre-computed query embedding. If not supplied, it is computed
            from ``query_text`` via the stored embedder.
        where : dict, optional
            ChromaDB metadata filter forwarded to semantic search.

        Returns
        -------
        list[dict]
            Up to ``config.max_candidates`` merged, deduplicated results,
            each with an ``rrf_score`` key.
        """
        if query_embedding is None:
            query_embedding = self.embedder.embed_query(query_text)

        sem_results = self.semantic_search(query_embedding, where=where)
        kw_results  = self.keyword_search(query_text)

        logger.info(
            "Hybrid search: %d semantic + %d BM25 candidates.",
            len(sem_results), len(kw_results),
        )

        merged = _reciprocal_rank_fusion(
            [sem_results, kw_results],
            id_key="chunk_id",
            k=self.config.rrf_k,
        )
        top = merged[: self.config.max_candidates]
        logger.info("RRF merge: %d unique candidates (max=%d).", len(top), self.config.max_candidates)
        return top

    # ──────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _normalise_semantic(result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure the semantic result dict has a ``chunk_id`` key.
        ChromaDB may return it under ``"chunk_id"`` directly (set by our
        metadata builder) or as the document id.
        """
        if "chunk_id" not in result:
            result = {**result, "chunk_id": result.get("id", "")}
        return result
