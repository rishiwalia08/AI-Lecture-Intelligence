"""
tests/test_hybrid_search.py
-----------------------------
Unit tests for src.retrieval.hybrid_search

BM25 tests run against actual rank_bm25.
Semantic + hybrid tests mock the ChromaManager and Embedder.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from src.retrieval.hybrid_search import (
    BM25Index,
    HybridConfig,
    HybridSearcher,
    _reciprocal_rank_fusion,
)


# ──────────────────────────────────────────────────────────────
# Fixtures / helpers
# ──────────────────────────────────────────────────────────────
def _make_chunk_dict(idx: int, lecture_id: str = "lecture_01") -> Dict[str, Any]:
    return {
        "chunk_id":   f"{lecture_id}_chunk_{idx:03d}",
        "text":       f"This is chunk number {idx} about algorithms and data structures.",
        "lecture_id": lecture_id,
        "start_time": float(idx * 10),
        "end_time":   float((idx + 1) * 10),
    }


class _MockChunk:
    """Duck-type a Chunk object for BM25Index.build()."""
    def __init__(self, idx: int, lecture_id: str = "lecture_01") -> None:
        self.chunk_id   = f"{lecture_id}_chunk_{idx:03d}"
        self.text       = f"This is chunk number {idx} about algorithms and data structures."
        self.lecture_id = lecture_id
        self.start_time = float(idx * 10)
        self.end_time   = float((idx + 1) * 10)


SAMPLE_CHUNKS = [_MockChunk(i) for i in range(5)]
SAMPLE_DICTS  = [_make_chunk_dict(i) for i in range(5)]


def _mock_manager(results: List[Dict]) -> MagicMock:
    m = MagicMock()
    m.search.return_value = results
    return m


def _mock_embedder() -> MagicMock:
    e = MagicMock()
    e.embed_query.return_value = [0.1] * 16
    return e


# ──────────────────────────────────────────────────────────────
# BM25Index tests
# ──────────────────────────────────────────────────────────────
class TestBM25Index:
    def test_build_from_chunk_objects(self) -> None:
        idx = BM25Index()
        idx.build(SAMPLE_CHUNKS)
        assert idx.size == len(SAMPLE_CHUNKS)

    def test_build_from_dicts(self) -> None:
        idx = BM25Index()
        idx.build(SAMPLE_DICTS)
        assert idx.size == len(SAMPLE_DICTS)

    def test_search_returns_list(self) -> None:
        idx = BM25Index()
        idx.build(SAMPLE_CHUNKS)
        results = idx.search("algorithms", top_k=3)
        assert isinstance(results, list)

    def test_search_respects_top_k(self) -> None:
        idx = BM25Index()
        idx.build(SAMPLE_CHUNKS)
        results = idx.search("chunk algorithms", top_k=2)
        assert len(results) <= 2

    def test_search_returns_matching_terms(self) -> None:
        """BM25 should return a result when the query term is selective (not in all docs)."""
        # Only chunk 0 contains the word 'zerospecial' — BM25 IDF will be non-zero
        chunks = [_MockChunk(0), _MockChunk(1), _MockChunk(2)]
        chunks[0].text = "zerospecial unique term about KMP algorithm"
        idx = BM25Index()
        idx.build(chunks)
        results = idx.search("zerospecial", top_k=5)
        assert len(results) >= 1
        assert results[0]["chunk_id"] == chunks[0].chunk_id

    def test_search_zero_score_filtered(self) -> None:
        idx = BM25Index()
        # Build with chunks about "xyz_zzzz" — query about unrelated topic
        # BM25 should return empty (score 0 for completely unrelated query)
        idx.build([_MockChunk(0)])
        results = idx.search("quantum_physics_asdqwe", top_k=5)
        # Should return 0 or only positive-score items
        assert all(r["bm25_score"] > 0 for r in results)

    def test_search_before_build_returns_empty(self) -> None:
        idx = BM25Index()
        results = idx.search("anything", top_k=5)
        assert results == []

    def test_result_has_required_keys(self) -> None:
        idx = BM25Index()
        idx.build(SAMPLE_CHUNKS)
        results = idx.search("data structures", top_k=3)
        if results:
            for key in ("chunk_id", "text", "lecture_id", "start_time", "end_time", "bm25_score"):
                assert key in results[0]


# ──────────────────────────────────────────────────────────────
# RRF helper tests
# ──────────────────────────────────────────────────────────────
class TestRRF:
    def test_single_list_passthrough(self) -> None:
        lst = [{"chunk_id": f"c{i}", "text": f"t{i}"} for i in range(3)]
        merged = _reciprocal_rank_fusion([lst])
        assert len(merged) == 3

    def test_deduplicates_across_lists(self) -> None:
        common = {"chunk_id": "common", "text": "shared"}
        list1  = [common, {"chunk_id": "a", "text": "ta"}]
        list2  = [common, {"chunk_id": "b", "text": "tb"}]
        merged = _reciprocal_rank_fusion([list1, list2])
        ids    = [m["chunk_id"] for m in merged]
        assert ids.count("common") == 1

    def test_top_ranked_in_both_gets_higher_score(self) -> None:
        """A chunk top-ranked in both lists should outscore one in only one."""
        winner = {"chunk_id": "w", "text": "winner"}
        loser  = {"chunk_id": "l", "text": "loser"}
        list1  = [winner, loser]
        list2  = [winner, {"chunk_id": "z", "text": "other"}]
        merged = _reciprocal_rank_fusion([list1, list2])
        scores = {m["chunk_id"]: m["rrf_score"] for m in merged}
        assert scores["w"] > scores["l"]

    def test_rrf_score_key_present(self) -> None:
        lst    = [{"chunk_id": "x", "text": "hello"}]
        merged = _reciprocal_rank_fusion([lst])
        assert "rrf_score" in merged[0]

    def test_empty_lists(self) -> None:
        merged = _reciprocal_rank_fusion([[], []])
        assert merged == []


# ──────────────────────────────────────────────────────────────
# HybridSearcher tests (mocked)
# ──────────────────────────────────────────────────────────────
class TestHybridSearcher:
    def _make_searcher(self, sem_results: List[Dict]) -> HybridSearcher:
        manager  = _mock_manager([{**r, "chunk_id": r.get("chunk_id", r.get("id", ""))} for r in sem_results])
        embedder = _mock_embedder()
        cfg      = HybridConfig(semantic_top_k=3, bm25_top_k=3, max_candidates=10)
        s        = HybridSearcher(manager, embedder, cfg)
        s.bm25.build(SAMPLE_CHUNKS)
        return s

    def test_semantic_search_returns_list(self) -> None:
        sem = [{"chunk_id": "c0", "text": "t0", "lecture_id": "l1",
                "start_time": 0.0, "end_time": 10.0, "score": 0.9}]
        s = self._make_searcher(sem)
        results = s.semantic_search([0.1] * 16)
        assert isinstance(results, list)

    def test_keyword_search_returns_list(self) -> None:
        s = self._make_searcher([])
        results = s.keyword_search("algorithms")
        assert isinstance(results, list)

    def test_hybrid_search_returns_list(self) -> None:
        sem = [{"chunk_id": "c0", "text": "algorithms", "lecture_id": "l1",
                "start_time": 0.0, "end_time": 10.0, "score": 0.8}]
        s = self._make_searcher(sem)
        results = s.hybrid_search("algorithms", query_embedding=[0.1] * 16)
        assert isinstance(results, list)

    def test_hybrid_deduplicates(self) -> None:
        """Same chunk_id from both sources appears only once."""
        chunk = {"chunk_id": "shared_0", "text": "algorithms data structures",
                 "lecture_id": "l1", "start_time": 0.0, "end_time": 10.0, "score": 0.9}
        manager  = _mock_manager([chunk])
        embedder = _mock_embedder()
        s        = HybridSearcher(manager, embedder, HybridConfig())
        s.bm25.build(SAMPLE_CHUNKS)
        results = s.hybrid_search("algorithms", query_embedding=[0.1] * 16)
        ids = [r["chunk_id"] for r in results]
        assert ids.count("shared_0") <= 1

    def test_hybrid_embedding_auto_computed(self) -> None:
        """If query_embedding is None, embedder.embed_query() should be called."""
        sem = [{"chunk_id": "c0", "text": "t0", "lecture_id": "l1",
                "start_time": 0.0, "end_time": 10.0, "score": 0.7}]
        manager  = _mock_manager(sem)
        embedder = _mock_embedder()
        s = HybridSearcher(manager, embedder, HybridConfig())
        s.bm25.build(SAMPLE_CHUNKS)
        s.hybrid_search("test query")           # no query_embedding supplied
        embedder.embed_query.assert_called_once()
