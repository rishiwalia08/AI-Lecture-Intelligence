"""
tests/test_audio_normalizer.py
--------------------------------
Unit tests for src.audio_processing.audio_normalizer
"""

from __future__ import annotations

import struct
import wave
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from src.audio_processing.audio_normalizer import (
    normalize_audio,
    validate_audio_format,
)


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────
def _make_wav(path: Path, sr: int = 44100, channels: int = 2, duration: float = 1.0) -> Path:
    """Create a minimal WAV file for testing."""
    samples = np.zeros(int(sr * duration * channels), dtype=np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())
    return path


# ──────────────────────────────────────────────────────────────
# normalize_audio tests
# ──────────────────────────────────────────────────────────────
class TestNormalizeAudio:
    def test_normalizes_stereo_44khz_to_mono_16khz(self, tmp_path: Path) -> None:
        src = _make_wav(tmp_path / "input.wav", sr=44100, channels=2)
        dst = tmp_path / "output.wav"

        success = normalize_audio(src, dst)

        assert success is True
        assert dst.exists()
        info = sf.info(str(dst))
        assert info.samplerate == 16000
        assert info.channels == 1

    def test_already_correct_format_passes(self, tmp_path: Path) -> None:
        src = _make_wav(tmp_path / "input.wav", sr=16000, channels=1)
        dst = tmp_path / "output.wav"

        success = normalize_audio(src, dst, target_sr=16000)

        assert success is True
        info = sf.info(str(dst))
        assert info.samplerate == 16000
        assert info.channels == 1

    def test_missing_input_returns_false(self, tmp_path: Path) -> None:
        dst = tmp_path / "output.wav"
        result = normalize_audio(tmp_path / "ghost.wav", dst)
        assert result is False

    def test_creates_output_directory(self, tmp_path: Path) -> None:
        src = _make_wav(tmp_path / "input.wav", sr=16000, channels=1)
        dst = tmp_path / "new_dir" / "nested" / "output.wav"

        success = normalize_audio(src, dst)

        assert success is True
        assert dst.exists()


# ──────────────────────────────────────────────────────────────
# validate_audio_format tests
# ──────────────────────────────────────────────────────────────
class TestValidateAudioFormat:
    def test_valid_file_returns_true(self, tmp_path: Path) -> None:
        path = _make_wav(tmp_path / "valid.wav", sr=16000, channels=1)
        result = validate_audio_format(path)
        assert result["is_valid"] is True
        assert result["issues"] == []

    def test_wrong_sample_rate_detected(self, tmp_path: Path) -> None:
        path = _make_wav(tmp_path / "hd.wav", sr=44100, channels=1)
        result = validate_audio_format(path, expected_sr=16000)
        assert result["is_valid"] is False
        assert any("sample_rate" in issue for issue in result["issues"])

    def test_stereo_detected(self, tmp_path: Path) -> None:
        path = _make_wav(tmp_path / "stereo.wav", sr=16000, channels=2)
        result = validate_audio_format(path, expected_channels=1)
        assert result["is_valid"] is False
        assert any("channels" in issue for issue in result["issues"])

    def test_missing_file_returns_false(self, tmp_path: Path) -> None:
        result = validate_audio_format(tmp_path / "missing.wav")
        assert result["is_valid"] is False
        assert result["issues"] != []
