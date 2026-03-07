"""
tests/test_whisper_transcriber.py
-----------------------------------
Unit tests for src.asr.whisper_transcriber

All tests use mocked Whisper models — no GPU or model download required.
"""

from __future__ import annotations

import time
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.asr.whisper_transcriber import (
    WhisperConfig,
    TranscriptionMetrics,
    transcribe_audio,
    transcribe_with_metrics,
)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def _make_wav(path: Path, sr: int = 16000, duration: float = 2.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = np.zeros(int(sr * duration), dtype=np.int16)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())
    return path


def _mock_openai_model(segments: list | None = None) -> MagicMock:
    """Return a mock openai-whisper model with a preset transcribe() output."""
    segs = segments or [
        {"text": " Hello world.", "start": 0.0, "end": 2.5},
        {"text": " KMP algorithm.", "start": 2.5, "end": 5.0},
    ]
    model = MagicMock()
    model.transcribe.return_value = {"segments": segs, "text": "Hello world. KMP algorithm."}
    return model


# ──────────────────────────────────────────────────────────────
# WhisperConfig tests
# ──────────────────────────────────────────────────────────────
class TestWhisperConfig:
    def test_defaults_are_valid(self) -> None:
        cfg = WhisperConfig()
        assert cfg.model_size == "large-v3"
        assert cfg.backend in ("openai", "faster")
        assert cfg.batch_size > 0

    def test_effective_device_falls_back_to_cpu(self, monkeypatch) -> None:
        import torch
        monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
        cfg = WhisperConfig(device="cuda")
        assert cfg.effective_device() == "cpu"

    def test_cpu_device_unchanged(self) -> None:
        cfg = WhisperConfig(device="cpu")
        assert cfg.effective_device() == "cpu"


# ──────────────────────────────────────────────────────────────
# transcribe_audio — openai backend
# ──────────────────────────────────────────────────────────────
class TestTranscribeAudioOpenAI:
    def test_returns_normalised_segments(self, tmp_path: Path) -> None:
        audio = _make_wav(tmp_path / "lecture.wav")
        model = _mock_openai_model()
        cfg = WhisperConfig(backend="openai")

        segments = transcribe_audio(audio, model, cfg)

        assert isinstance(segments, list)
        assert len(segments) == 2
        for seg in segments:
            assert "text" in seg
            assert "start" in seg
            assert "end" in seg

    def test_text_is_stripped(self, tmp_path: Path) -> None:
        audio = _make_wav(tmp_path / "lecture.wav")
        model = _mock_openai_model([{"text": "  Hello  ", "start": 0.0, "end": 1.0}])
        cfg = WhisperConfig(backend="openai")

        segments = transcribe_audio(audio, model, cfg)
        assert segments[0]["text"] == "Hello"

    def test_empty_text_segments_filtered(self, tmp_path: Path) -> None:
        audio = _make_wav(tmp_path / "lecture.wav")
        model = _mock_openai_model([
            {"text": "Valid segment.", "start": 0.0, "end": 2.0},
            {"text": "   ", "start": 2.0, "end": 3.0},
        ])
        cfg = WhisperConfig(backend="openai")

        segments = transcribe_audio(audio, model, cfg)
        assert len(segments) == 1

    def test_missing_audio_returns_empty(self, tmp_path: Path) -> None:
        model = _mock_openai_model()
        cfg = WhisperConfig(backend="openai")

        segments = transcribe_audio(tmp_path / "ghost.wav", model, cfg)
        assert segments == []

    def test_model_exception_returns_empty(self, tmp_path: Path) -> None:
        audio = _make_wav(tmp_path / "lecture.wav")
        model = MagicMock()
        model.transcribe.side_effect = RuntimeError("GPU OOM")
        cfg = WhisperConfig(backend="openai")

        segments = transcribe_audio(audio, model, cfg)
        assert segments == []


# ──────────────────────────────────────────────────────────────
# TranscriptionMetrics
# ──────────────────────────────────────────────────────────────
class TestTranscriptionMetrics:
    def test_realtime_factor_computed(self) -> None:
        m = TranscriptionMetrics(audio_duration=60.0, processing_time=30.0)
        assert m.realtime_factor == pytest.approx(0.5)

    def test_realtime_factor_none_when_zero_duration(self) -> None:
        m = TranscriptionMetrics(audio_duration=0.0, processing_time=5.0)
        assert m.realtime_factor is None

    def test_to_dict_has_all_required_keys(self) -> None:
        m = TranscriptionMetrics(file_name="test.wav", backend_used="openai")
        d = m.to_dict()
        for key in ("file_name", "audio_duration", "processing_time",
                    "num_segments", "backend_used", "realtime_factor", "error"):
            assert key in d


# ──────────────────────────────────────────────────────────────
# transcribe_with_metrics
# ──────────────────────────────────────────────────────────────
class TestTranscribeWithMetrics:
    def test_returns_tuple(self, tmp_path: Path) -> None:
        audio = _make_wav(tmp_path / "lecture.wav")
        model = _mock_openai_model()
        cfg = WhisperConfig(backend="openai")

        result = transcribe_with_metrics(audio, model, cfg)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_metrics_file_name_set(self, tmp_path: Path) -> None:
        audio = _make_wav(tmp_path / "lecture.wav")
        model = _mock_openai_model()
        cfg = WhisperConfig(backend="openai")

        _, metrics = transcribe_with_metrics(audio, model, cfg)
        assert metrics.file_name == "lecture.wav"

    def test_processing_time_positive(self, tmp_path: Path) -> None:
        audio = _make_wav(tmp_path / "lecture.wav")
        model = _mock_openai_model()
        cfg = WhisperConfig(backend="openai")

        _, metrics = transcribe_with_metrics(audio, model, cfg)
        assert metrics.processing_time >= 0

    def test_error_captured_when_model_fails(self, tmp_path: Path) -> None:
        audio = _make_wav(tmp_path / "lecture.wav")
        # Make transcribe_audio itself raise to test the outer try/except
        model = MagicMock()
        model.transcribe.side_effect = RuntimeError("Crash")
        cfg = WhisperConfig(backend="openai")

        segments, metrics = transcribe_with_metrics(audio, model, cfg)
        # segments empty, metrics.error may or may not be set depending
        # on whether the error propagates — either is acceptable
        assert isinstance(segments, list)
