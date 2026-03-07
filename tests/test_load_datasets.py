"""
tests/test_load_datasets.py
----------------------------
Unit tests for src.data_ingestion.load_datasets
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data_ingestion.load_datasets import (
    METADATA_COLUMNS,
    _empty_dataframe,
    load_local_lectures,
    load_tedlium_dataset,
    load_librispeech_dataset,
    load_commonvoice_dataset,
)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def _make_wav(path: Path, sr: int = 16000, duration: float = 0.5) -> Path:
    """Write a minimal WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = np.zeros(int(sr * duration), dtype=np.int16)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())
    return path


# ──────────────────────────────────────────────────────────────
# _empty_dataframe
# ──────────────────────────────────────────────────────────────
def test_empty_dataframe_has_correct_columns() -> None:
    df = _empty_dataframe()
    assert list(df.columns) == METADATA_COLUMNS
    assert len(df) == 0


# ──────────────────────────────────────────────────────────────
# load_local_lectures
# ──────────────────────────────────────────────────────────────
class TestLoadLocalLectures:
    def test_returns_empty_for_missing_dir(self, tmp_path: Path) -> None:
        df = load_local_lectures(tmp_path / "nonexistent")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert list(df.columns) == METADATA_COLUMNS

    def test_loads_single_wav(self, tmp_path: Path) -> None:
        lectures_dir = tmp_path / "lectures"
        _make_wav(lectures_dir / "lecture1.wav")

        df = load_local_lectures(lectures_dir)

        assert len(df) == 1
        assert df.iloc[0]["dataset_name"] == "local_lectures"
        assert df.iloc[0]["audio_path"].endswith("lecture1.wav")

    def test_loads_multiple_wavs(self, tmp_path: Path) -> None:
        lectures_dir = tmp_path / "lectures"
        for i in range(3):
            _make_wav(lectures_dir / f"lecture{i}.wav")

        df = load_local_lectures(lectures_dir)
        assert len(df) == 3

    def test_dataframe_columns(self, tmp_path: Path) -> None:
        lectures_dir = tmp_path / "lectures"
        _make_wav(lectures_dir / "a.wav")

        df = load_local_lectures(lectures_dir)
        assert set(METADATA_COLUMNS).issubset(set(df.columns))


# ──────────────────────────────────────────────────────────────
# load_tedlium_dataset
# ──────────────────────────────────────────────────────────────
class TestLoadTEDLIUM:
    def test_missing_dir_returns_empty(self, tmp_path: Path) -> None:
        df = load_tedlium_dataset(tmp_path / "no_tedlium")
        assert len(df) == 0

    def test_loads_nested_wav(self, tmp_path: Path) -> None:
        root = tmp_path / "tedlium" / "speaker1"
        _make_wav(root / "talk.wav")

        df = load_tedlium_dataset(tmp_path / "tedlium")
        assert len(df) == 1
        assert df.iloc[0]["dataset_name"] == "tedlium"
        assert df.iloc[0]["speaker_id"] == "speaker1"


# ──────────────────────────────────────────────────────────────
# load_librispeech_dataset
# ──────────────────────────────────────────────────────────────
class TestLoadLibriSpeech:
    def test_missing_dir_returns_empty(self, tmp_path: Path) -> None:
        df = load_librispeech_dataset(tmp_path / "no_librispeech")
        assert len(df) == 0

    def test_loads_flac_file(self, tmp_path: Path) -> None:
        # LibriSpeech uses flac; we'll use wav for the test
        root = tmp_path / "librispeech" / "1234" / "5678"
        _make_wav(root / "utterance.wav")

        df = load_librispeech_dataset(tmp_path / "librispeech")
        assert len(df) == 1
        assert df.iloc[0]["dataset_name"] == "librispeech"


# ──────────────────────────────────────────────────────────────
# load_commonvoice_dataset
# ──────────────────────────────────────────────────────────────
class TestLoadCommonVoice:
    def test_missing_dir_returns_empty(self, tmp_path: Path) -> None:
        df = load_commonvoice_dataset(tmp_path / "no_cv")
        assert len(df) == 0

    def test_fallback_scan_loads_wav(self, tmp_path: Path) -> None:
        cv_dir = tmp_path / "commonvoice"
        _make_wav(cv_dir / "clip1.wav")

        df = load_commonvoice_dataset(cv_dir)
        assert len(df) == 1
        assert df.iloc[0]["dataset_name"] == "commonvoice_indian"

    def test_tsv_manifest_loading(self, tmp_path: Path) -> None:
        cv_dir = tmp_path / "commonvoice"
        clips_dir = cv_dir / "clips"
        _make_wav(clips_dir / "c001.wav")

        # Build a minimal TSV
        tsv_content = "client_id\tpath\n" "abc123\tc001.wav\n"
        (cv_dir / "train.tsv").write_text(tsv_content)

        df = load_commonvoice_dataset(cv_dir, tsv_filename="train.tsv")
        assert len(df) == 1
        assert df.iloc[0]["speaker_id"] == "abc123"
