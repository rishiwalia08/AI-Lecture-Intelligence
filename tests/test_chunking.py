"""
tests/test_chunking.py
------------------------
Unit tests for src.embedding.chunking
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.embedding.chunking import (
    Chunk,
    ChunkConfig,
    create_chunks,
    load_chunks,
    save_chunks,
)

# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────
def _make_transcript(
    lecture_id: str = "lecture_01",
    num_segments: int = 10,
    words_per_segment: int = 60,
) -> dict:
    """Build a synthetic transcript for testing."""
    segments = []
    for i in range(num_segments):
        text = " ".join([f"word{i}_{j}" for j in range(words_per_segment)])
        segments.append({
            "segment_id": f"{i + 1:03d}",
            "text":       text,
            "start":      float(i * 10),
            "end":        float((i + 1) * 10),
        })
    return {"lecture_id": lecture_id, "segments": segments}


SMALL_TRANSCRIPT = {
    "lecture_id": "lecture_01",
    "segments": [
        {"segment_id": "001", "text": "The KMP algorithm is used for pattern matching.",  "start": 0.0,  "end": 6.2},
        {"segment_id": "002", "text": "It runs in linear time compared to naive O(nm).", "start": 6.2,  "end": 9.8},
        {"segment_id": "003", "text": "The prefix function avoids redundant comparisons.", "start": 9.8,  "end": 14.5},
    ],
}


# ──────────────────────────────────────────────────────────────
# ChunkConfig tests
# ──────────────────────────────────────────────────────────────
class TestChunkConfig:
    def test_defaults_valid(self) -> None:
        cfg = ChunkConfig()
        assert cfg.chunk_size > cfg.chunk_overlap
        assert cfg.min_chunk_tokens >= 0

    def test_overlap_ge_size_raises(self) -> None:
        with pytest.raises(ValueError):
            ChunkConfig(chunk_size=100, chunk_overlap=100)

    def test_overlap_gt_size_raises(self) -> None:
        with pytest.raises(ValueError):
            ChunkConfig(chunk_size=50, chunk_overlap=60)


# ──────────────────────────────────────────────────────────────
# create_chunks tests
# ──────────────────────────────────────────────────────────────
class TestCreateChunks:
    def test_returns_list(self) -> None:
        chunks = create_chunks(SMALL_TRANSCRIPT)
        assert isinstance(chunks, list)

    def test_empty_segments_returns_empty(self) -> None:
        t = {"lecture_id": "x", "segments": []}
        assert create_chunks(t) == []

    def test_chunk_id_format(self) -> None:
        cfg = ChunkConfig(chunk_size=10, chunk_overlap=2, min_chunk_tokens=1)
        chunks = create_chunks(SMALL_TRANSCRIPT, cfg)
        assert chunks[0].chunk_id.startswith("lecture_01_chunk_")
        assert "_chunk_001" in chunks[0].chunk_id

    def test_lecture_id_propagated(self) -> None:
        chunks = create_chunks(SMALL_TRANSCRIPT)
        for c in chunks:
            assert c.lecture_id == "lecture_01"

    def test_timestamps_cover_segments(self) -> None:
        chunks = create_chunks(SMALL_TRANSCRIPT)
        assert chunks[0].start_time == pytest.approx(0.0)
        assert chunks[-1].end_time  == pytest.approx(14.5)

    def test_token_count_leq_chunk_size(self) -> None:
        cfg = ChunkConfig(chunk_size=20, chunk_overlap=5, min_chunk_tokens=1)
        chunks = create_chunks(SMALL_TRANSCRIPT, cfg)
        for c in chunks:
            assert c.token_count <= cfg.chunk_size

    def test_overlap_tokens_shared(self) -> None:
        """Last overlap tokens of chunk N should equal first tokens of chunk N+1."""
        cfg = ChunkConfig(chunk_size=10, chunk_overlap=3, min_chunk_tokens=1)
        big = _make_transcript(num_segments=3, words_per_segment=20)
        chunks = create_chunks(big, cfg)
        if len(chunks) >= 2:
            tail  = chunks[0].text.split()[-cfg.chunk_overlap:]
            head  = chunks[1].text.split()[:cfg.chunk_overlap]
            assert tail == head

    def test_large_transcript_multiple_chunks(self) -> None:
        t = _make_transcript(num_segments=10, words_per_segment=60)
        cfg = ChunkConfig(chunk_size=100, chunk_overlap=10, min_chunk_tokens=5)
        chunks = create_chunks(t, cfg)
        assert len(chunks) > 1

    def test_segment_ids_populated(self) -> None:
        chunks = create_chunks(SMALL_TRANSCRIPT)
        for c in chunks:
            assert isinstance(c.segment_ids, list)
            assert len(c.segment_ids) >= 1

    def test_chunk_index_monotonic(self) -> None:
        cfg = ChunkConfig(chunk_size=10, chunk_overlap=2, min_chunk_tokens=1)
        chunks = create_chunks(SMALL_TRANSCRIPT, cfg)
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))


# ──────────────────────────────────────────────────────────────
# save_chunks / load_chunks round-trip
# ──────────────────────────────────────────────────────────────
class TestChunkIO:
    def test_save_creates_file(self, tmp_path: Path) -> None:
        chunks = create_chunks(SMALL_TRANSCRIPT)
        out    = save_chunks(chunks, tmp_path)
        assert out.exists()
        assert out.name == "lecture_01_chunks.json"

    def test_saved_file_is_valid_json(self, tmp_path: Path) -> None:
        chunks = create_chunks(SMALL_TRANSCRIPT)
        out    = save_chunks(chunks, tmp_path)
        data   = json.loads(out.read_text())
        assert "chunks" in data
        assert data["lecture_id"] == "lecture_01"

    def test_load_round_trips(self, tmp_path: Path) -> None:
        chunks = create_chunks(SMALL_TRANSCRIPT)
        out    = save_chunks(chunks, tmp_path)
        loaded = load_chunks(out)
        assert len(loaded) == len(chunks)
        assert loaded[0].chunk_id == chunks[0].chunk_id
        assert loaded[0].text     == chunks[0].text

    def test_load_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_chunks(tmp_path / "ghost.json")

    def test_save_empty_list_is_safe(self, tmp_path: Path) -> None:
        result = save_chunks([], tmp_path)
        assert result == tmp_path  # returns dir, no file written
