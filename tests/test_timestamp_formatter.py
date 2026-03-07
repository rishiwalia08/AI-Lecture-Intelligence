"""
tests/test_timestamp_formatter.py
-----------------------------------
Unit tests for src.asr.timestamp_formatter

Pure-logic tests — no model or GPU required.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.asr.timestamp_formatter import (
    ValidationResult,
    format_transcript,
    format_segment_file,
    load_transcript,
    save_full_transcript,
    save_segments,
    validate_transcript,
)


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────
SAMPLE_SEGMENTS = [
    {"text": "The KMP algorithm is used for pattern matching.", "start": 0.0, "end": 6.2},
    {"text": "It runs in linear time.", "start": 6.2, "end": 9.8},
    {"text": "The prefix function avoids redundant comparisons.", "start": 9.8, "end": 14.5},
]


# ──────────────────────────────────────────────────────────────
# format_transcript
# ──────────────────────────────────────────────────────────────
class TestFormatTranscript:
    def test_returns_dict(self) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS)
        assert isinstance(t, dict)

    def test_lecture_id_preserved(self) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS)
        assert t["lecture_id"] == "lecture_01"

    def test_num_segments_matches(self) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS)
        assert t["num_segments"] == len(SAMPLE_SEGMENTS)

    def test_segments_have_required_keys(self) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS)
        for seg in t["segments"]:
            for key in ("segment_id", "text", "start", "end"):
                assert key in seg

    def test_segment_ids_are_zero_padded(self) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS)
        assert t["segments"][0]["segment_id"] == "001"
        assert t["segments"][2]["segment_id"] == "003"

    def test_empty_segments_list(self) -> None:
        t = format_transcript("empty_lecture", [])
        assert t["num_segments"] == 0
        assert t["total_duration"] == 0.0

    def test_total_duration_equals_last_end(self) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS)
        assert t["total_duration"] == pytest.approx(14.5)

    def test_metadata_merged(self) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS, metadata={"dataset": "tedlium"})
        assert t["dataset"] == "tedlium"

    def test_text_stripped(self) -> None:
        segs = [{"text": "  padded  ", "start": 0.0, "end": 1.0}]
        t = format_transcript("x", segs)
        assert t["segments"][0]["text"] == "padded"


# ──────────────────────────────────────────────────────────────
# format_segment_file
# ──────────────────────────────────────────────────────────────
class TestFormatSegmentFile:
    def test_contains_all_fields(self) -> None:
        seg = {"segment_id": "001", "text": "Hello.", "start": 0.0, "end": 2.0}
        result = format_segment_file("lecture_01", seg)
        assert result["lecture_id"] == "lecture_01"
        assert result["segment_id"] == "001"
        assert result["text"] == "Hello."


# ──────────────────────────────────────────────────────────────
# save_full_transcript
# ──────────────────────────────────────────────────────────────
class TestSaveFullTranscript:
    def test_file_created(self, tmp_path: Path) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS)
        out = save_full_transcript(t, tmp_path)
        assert out.exists()
        assert out.name == "lecture_01_transcript.json"

    def test_file_is_valid_json(self, tmp_path: Path) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS)
        out = save_full_transcript(t, tmp_path)
        loaded = json.loads(out.read_text())
        assert loaded["lecture_id"] == "lecture_01"

    def test_creates_output_directory(self, tmp_path: Path) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS)
        nested = tmp_path / "deep" / "dir"
        save_full_transcript(t, nested)
        assert (nested / "lecture_01_transcript.json").exists()


# ──────────────────────────────────────────────────────────────
# save_segments
# ──────────────────────────────────────────────────────────────
class TestSaveSegments:
    def test_correct_number_of_files(self, tmp_path: Path) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS)
        written = save_segments(t, tmp_path)
        assert len(written) == len(SAMPLE_SEGMENTS)

    def test_files_are_valid_json(self, tmp_path: Path) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS)
        written = save_segments(t, tmp_path)
        for path in written:
            data = json.loads(path.read_text())
            assert "text" in data
            assert "start" in data
            assert "end" in data

    def test_file_naming_convention(self, tmp_path: Path) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS)
        written = save_segments(t, tmp_path)
        names = [p.name for p in written]
        assert "lecture_01_segment_001.json" in names
        assert "lecture_01_segment_003.json" in names

    def test_segments_stored_in_lecture_subfolder(self, tmp_path: Path) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS)
        save_segments(t, tmp_path)
        assert (tmp_path / "lecture_01").is_dir()


# ──────────────────────────────────────────────────────────────
# load_transcript
# ──────────────────────────────────────────────────────────────
class TestLoadTranscript:
    def test_round_trips_correctly(self, tmp_path: Path) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS)
        save_full_transcript(t, tmp_path)
        loaded = load_transcript(tmp_path / "lecture_01_transcript.json")
        assert loaded["lecture_id"] == "lecture_01"
        assert loaded["num_segments"] == 3

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_transcript(tmp_path / "missing.json")


# ──────────────────────────────────────────────────────────────
# validate_transcript
# ──────────────────────────────────────────────────────────────
class TestValidateTranscript:
    def test_valid_transcript_passes(self) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS)
        result = validate_transcript(t)
        assert result.is_valid is True
        assert result.issues == []

    def test_missing_lecture_id_fails(self) -> None:
        t = format_transcript("", SAMPLE_SEGMENTS)
        result = validate_transcript(t)
        assert result.is_valid is False
        assert any("lecture_id" in issue for issue in result.issues)

    def test_empty_segments_fails(self) -> None:
        t = format_transcript("lecture_01", [])
        result = validate_transcript(t)
        assert result.is_valid is False

    def test_empty_text_detected(self) -> None:
        segs = [
            {"text": "Valid text.", "start": 0.0, "end": 2.0},
            {"text": "   ", "start": 2.0, "end": 4.0},
        ]
        t = format_transcript("lecture_01", segs)
        result = validate_transcript(t)
        assert result.is_valid is False
        assert result.num_empty > 0

    def test_out_of_order_timestamps_detected(self) -> None:
        segs = [
            {"text": "First.", "start": 5.0, "end": 8.0},
            {"text": "Second.", "start": 1.0, "end": 4.0},   # start < prev_start
        ]
        t = format_transcript("lecture_01", segs)
        result = validate_transcript(t)
        assert result.is_valid is False
        assert result.num_ordering_errors > 0

    def test_start_greater_than_end_detected(self) -> None:
        # Inject a bad segment directly (bypass format_transcript normalisation)
        t = {
            "lecture_id": "lecture_01",
            "num_segments": 1,
            "total_duration": 5.0,
            "segments": [{"segment_id": "001", "text": "Bad.", "start": 9.0, "end": 3.0}],
        }
        result = validate_transcript(t)
        assert result.is_valid is False
        assert result.num_ordering_errors > 0

    def test_num_segments_counted(self) -> None:
        t = format_transcript("lecture_01", SAMPLE_SEGMENTS)
        result = validate_transcript(t)
        assert result.num_segments == 3
