"""
tests/test_chroma_manager.py
------------------------------
Unit tests for src.vectorstore.chroma_manager

Uses ChromaDB's EphemeralClient (in-memory) — no disk writes, no GPU needed.

Note: ChromaDB uses pydantic v1 internally which is not compatible with
Python 3.14+. Tests are automatically skipped on Python ≥ 3.14.
Use Python ≤ 3.12 for full test coverage.
"""

from __future__ import annotations

import sys
import pytest

if sys.version_info >= (3, 14):
    pytest.skip(
        "chromadb requires pydantic v1 which is incompatible with Python 3.14+. "
        "Run on Python ≤ 3.12 to execute these tests.",
        allow_module_level=True,
    )

from typing import List

import numpy as np
import pytest

from src.vectorstore.chroma_manager import ChromaConfig, ChromaManager
from src.embedding.chunking import Chunk


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
DIM = 16  # small dim for fast tests


def _rand_vec(dim: int = DIM) -> List[float]:
    return np.random.rand(dim).tolist()


def _make_chunk(idx: int, lecture_id: str = "lecture_01") -> Chunk:
    return Chunk(
        chunk_id    = f"{lecture_id}_chunk_{idx:03d}",
        text        = f"Segment text number {idx} about algorithms and data structures.",
        start_time  = float(idx * 10),
        end_time    = float((idx + 1) * 10),
        lecture_id  = lecture_id,
        segment_ids = [f"{idx:03d}"],
        chunk_index = idx,
        token_count = 9,
    )


def _make_metadata(chunk: Chunk) -> dict:
    return {
        "lecture_id":  chunk.lecture_id,
        "chunk_index": chunk.chunk_index,
        "start_time":  chunk.start_time,
        "end_time":    chunk.end_time,
        "timestamp":   "00:00",
        "token_count": chunk.token_count,
        "segment_ids": "|".join(chunk.segment_ids),
        "source_type": "audio_transcript",
        "speaker":     "professor",
    }


@pytest.fixture
def manager() -> ChromaManager:
    """An in-memory ChromaManager for testing (no disk I/O)."""
    cfg = ChromaConfig(collection_name=f"test_collection_{id(object())}")
    return ChromaManager(cfg, ephemeral=True)


def _populate(manager: ChromaManager, n: int = 5, lecture_id: str = "lecture_01"):
    chunks    = [_make_chunk(i, lecture_id) for i in range(n)]
    embeddings = [_rand_vec() for _ in range(n)]
    metadatas  = [_make_metadata(c) for c in chunks]
    manager.upsert(chunks, embeddings, metadatas)
    return chunks, embeddings


# ──────────────────────────────────────────────────────────────
# Upsert & count
# ──────────────────────────────────────────────────────────────
class TestUpsert:
    def test_count_increases_after_upsert(self, manager: ChromaManager) -> None:
        _populate(manager, n=3)
        assert manager.count() == 3

    def test_upsert_multiple_batches(self, manager: ChromaManager) -> None:
        _populate(manager, n=10)
        assert manager.count() == 10

    def test_upsert_empty_is_safe(self, manager: ChromaManager) -> None:
        result = manager.upsert([], [], [])
        assert result == 0
        assert manager.count() == 0

    def test_upsert_is_idempotent(self, manager: ChromaManager) -> None:
        """Upserting the same IDs twice should not increase count."""
        chunks, embs = _populate(manager, n=3)
        _populate(manager, n=3)   # same chunk_ids
        assert manager.count() == 3


# ──────────────────────────────────────────────────────────────
# Search
# ──────────────────────────────────────────────────────────────
class TestSearch:
    def test_search_returns_list(self, manager: ChromaManager) -> None:
        _populate(manager, n=5)
        results = manager.search(_rand_vec(), top_k=3)
        assert isinstance(results, list)

    def test_search_respects_top_k(self, manager: ChromaManager) -> None:
        _populate(manager, n=10)
        results = manager.search(_rand_vec(), top_k=4)
        assert len(results) <= 4

    def test_search_result_has_required_keys(self, manager: ChromaManager) -> None:
        _populate(manager, n=3)
        results = manager.search(_rand_vec(), top_k=1)
        assert len(results) >= 1
        for key in ("text", "lecture_id", "timestamp", "start_time", "end_time", "score", "chunk_id"):
            assert key in results[0]

    def test_search_empty_collection_returns_empty(self, manager: ChromaManager) -> None:
        results = manager.search(_rand_vec(), top_k=5)
        assert results == []

    def test_search_top_k_capped_to_available(self, manager: ChromaManager) -> None:
        _populate(manager, n=2)
        results = manager.search(_rand_vec(), top_k=100)
        assert len(results) <= 2

    def test_search_with_metadata_filter(self, manager: ChromaManager) -> None:
        _populate(manager, n=3, lecture_id="lecture_01")
        _populate(manager, n=3, lecture_id="lecture_02")
        results = manager.search(
            _rand_vec(), top_k=10,
            where={"lecture_id": "lecture_01"},
        )
        for r in results:
            assert r["lecture_id"] == "lecture_01"

    def test_score_is_float(self, manager: ChromaManager) -> None:
        _populate(manager, n=3)
        results = manager.search(_rand_vec(), top_k=1)
        assert isinstance(results[0]["score"], float)


# ──────────────────────────────────────────────────────────────
# Collection management
# ──────────────────────────────────────────────────────────────
class TestCollectionManagement:
    def test_delete_collection_resets_count(self, manager: ChromaManager) -> None:
        _populate(manager, n=5)
        assert manager.count() == 5
        manager.delete_collection()
        assert manager.count() == 0

    def test_get_stats_keys(self, manager: ChromaManager) -> None:
        stats = manager.get_stats()
        for key in ("collection_name", "num_vectors", "db_path", "distance_metric"):
            assert key in stats

    def test_get_stats_num_vectors_accurate(self, manager: ChromaManager) -> None:
        _populate(manager, n=7)
        stats = manager.get_stats()
        assert stats["num_vectors"] == 7
