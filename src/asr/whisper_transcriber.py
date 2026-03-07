"""
src/asr/whisper_transcriber.py
--------------------------------
Whisper ASR module for the Speech RAG system — Phase 2.

Supports both the standard ``openai-whisper`` library and the
``faster-whisper`` backend for GPU-accelerated inference.

Usage
-----
    from src.asr.whisper_transcriber import WhisperConfig, load_whisper_model, transcribe_with_metrics

    config = WhisperConfig(model_size="large-v3", device="cuda", backend="openai")
    model  = load_whisper_model(config)
    segments, metrics = transcribe_with_metrics("data/processed_audio/lecture01.wav", model, config)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch

from src.utils.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────
# Type aliases
# ──────────────────────────────────────────────────────────────
SegmentDict = Dict[str, Any]   # {"text": str, "start": float, "end": float}


# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
@dataclass
class WhisperConfig:
    """
    Configuration for the Whisper ASR backend.

    Attributes
    ----------
    model_size : str
        Whisper model variant — one of ``tiny``, ``base``, ``small``,
        ``medium``, ``large``, ``large-v2``, ``large-v3``.
    device : str
        Inference device.  ``"cuda"`` is used when available and
        requested; falls back to ``"cpu"`` automatically.
    backend : str
        ``"openai"`` for the standard ``openai-whisper`` package, or
        ``"faster"`` for ``faster-whisper`` (CTranslate2-based).
    batch_size : int
        Batch size for ``faster-whisper``; ignored by openai-whisper.
    language : str | None
        Force a specific language (e.g. ``"en"``).  ``None`` uses
        Whisper's auto-detection.
    task : str
        ``"transcribe"`` (default) or ``"translate"``.
    compute_type : str
        CTranslate2 quantisation type for ``faster-whisper``
        (``"float16"``, ``"int8_float16"``, ``"int8"``).
    """

    model_size: str = "large-v3"
    device: str = "cuda"
    backend: str = "openai"          # "openai" | "faster"
    batch_size: int = 4
    language: Optional[str] = "en"
    task: str = "transcribe"
    compute_type: str = "float16"    # faster-whisper only

    def effective_device(self) -> str:
        """Return ``"cuda"`` if available and requested, else ``"cpu"``."""
        if self.device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA requested but not available — falling back to CPU.")
            return "cpu"
        return self.device


# ──────────────────────────────────────────────────────────────
# Metrics
# ──────────────────────────────────────────────────────────────
@dataclass
class TranscriptionMetrics:
    """Per-file transcription performance record."""

    file_name: str = ""
    audio_duration: float = 0.0     # seconds
    processing_time: float = 0.0    # wall-clock seconds
    num_segments: int = 0
    backend_used: str = ""
    error: Optional[str] = None

    @property
    def realtime_factor(self) -> Optional[float]:
        """
        Processing-time / audio-duration ratio.

        Values < 1.0 indicate faster-than-real-time transcription.
        Returns ``None`` when audio duration is zero.
        """
        if self.audio_duration == 0:
            return None
        return self.processing_time / self.audio_duration

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_name":        self.file_name,
            "audio_duration":   round(self.audio_duration, 3),
            "processing_time":  round(self.processing_time, 3),
            "num_segments":     self.num_segments,
            "backend_used":     self.backend_used,
            "realtime_factor":  round(self.realtime_factor, 3) if self.realtime_factor is not None else None,
            "error":            self.error,
        }


# ──────────────────────────────────────────────────────────────
# Model loader
# ──────────────────────────────────────────────────────────────
def load_whisper_model(config: WhisperConfig) -> Any:
    """
    Load and return a Whisper model according to *config*.

    Parameters
    ----------
    config : WhisperConfig
        ASR configuration object.

    Returns
    -------
    Any
        An ``openai-whisper`` model object (``whisper.Whisper``) or a
        ``faster-whisper`` ``WhisperModel`` instance.

    Raises
    ------
    ImportError
        If the chosen backend library is not installed.
    RuntimeError
        If model loading fails for any other reason.
    """
    device = config.effective_device()
    logger.info(
        "Loading Whisper model — size='%s'  backend='%s'  device='%s'",
        config.model_size,
        config.backend,
        device,
    )

    if config.backend == "faster":
        return _load_faster_whisper(config, device)
    else:
        return _load_openai_whisper(config, device)


def _load_openai_whisper(config: WhisperConfig, device: str) -> Any:
    """Load a standard openai-whisper model."""
    try:
        import whisper  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "openai-whisper is not installed. Run: pip install openai-whisper"
        ) from exc

    try:
        model = whisper.load_model(config.model_size, device=device)
        logger.info("openai-whisper model '%s' loaded on %s.", config.model_size, device)
        return model
    except Exception as exc:
        raise RuntimeError(f"Failed to load openai-whisper model: {exc}") from exc


def _load_faster_whisper(config: WhisperConfig, device: str) -> Any:
    """Load a faster-whisper (CTranslate2) model."""
    try:
        from faster_whisper import WhisperModel  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "faster-whisper is not installed. Run: pip install faster-whisper"
        ) from exc

    compute_type = config.compute_type if device == "cuda" else "int8"
    try:
        model = WhisperModel(
            config.model_size,
            device=device,
            compute_type=compute_type,
        )
        logger.info(
            "faster-whisper model '%s' loaded on %s (compute_type=%s).",
            config.model_size, device, compute_type,
        )
        return model
    except Exception as exc:
        raise RuntimeError(f"Failed to load faster-whisper model: {exc}") from exc


# ──────────────────────────────────────────────────────────────
# Transcription
# ──────────────────────────────────────────────────────────────
def transcribe_audio(
    audio_path: str | Path,
    model: Any,
    config: WhisperConfig,
) -> List[SegmentDict]:
    """
    Transcribe an audio file and return a list of timestamped segments.

    Parameters
    ----------
    audio_path : str | Path
        Path to a 16 kHz mono WAV file (Phase 1 output).
    model : Any
        A loaded Whisper model (openai or faster-whisper).
    config : WhisperConfig
        ASR configuration used when the model was loaded.

    Returns
    -------
    list of dict
        Each element::

            {"text": "...", "start": 12.4, "end": 18.7}

    Returns an empty list on failure (errors are logged).
    """
    audio_path = Path(audio_path)

    if not audio_path.exists():
        logger.error("Audio file not found: '%s'", audio_path)
        return []

    logger.info("Transcribing '%s' (backend=%s)", audio_path.name, config.backend)

    try:
        if config.backend == "faster":
            return _transcribe_faster_whisper(audio_path, model, config)
        else:
            return _transcribe_openai_whisper(audio_path, model, config)
    except Exception as exc:  # noqa: BLE001
        logger.error("Transcription failed for '%s': %s", audio_path, exc)
        return []


def _transcribe_openai_whisper(
    audio_path: Path,
    model: Any,
    config: WhisperConfig,
) -> List[SegmentDict]:
    """Run openai-whisper transcription and normalise output."""
    result = model.transcribe(
        str(audio_path),
        language=config.language,
        task=config.task,
        verbose=False,
    )
    segments: List[SegmentDict] = [
        {
            "text":  seg["text"].strip(),
            "start": float(seg["start"]),
            "end":   float(seg["end"]),
        }
        for seg in result.get("segments", [])
        if seg.get("text", "").strip()
    ]
    logger.debug("openai-whisper: %d segments from '%s'.", len(segments), audio_path.name)
    return segments


def _transcribe_faster_whisper(
    audio_path: Path,
    model: Any,
    config: WhisperConfig,
) -> List[SegmentDict]:
    """Run faster-whisper transcription and normalise output."""
    raw_segments, _info = model.transcribe(
        str(audio_path),
        language=config.language,
        task=config.task,
        beam_size=5,
        vad_filter=True,
    )
    segments: List[SegmentDict] = [
        {
            "text":  seg.text.strip(),
            "start": float(seg.start),
            "end":   float(seg.end),
        }
        for seg in raw_segments
        if seg.text.strip()
    ]
    logger.debug("faster-whisper: %d segments from '%s'.", len(segments), audio_path.name)
    return segments


# ──────────────────────────────────────────────────────────────
# Metrics-wrapped transcription
# ──────────────────────────────────────────────────────────────
def transcribe_with_metrics(
    audio_path: str | Path,
    model: Any,
    config: WhisperConfig,
) -> Tuple[List[SegmentDict], TranscriptionMetrics]:
    """
    Transcribe *audio_path* and return segments plus performance metrics.

    Parameters
    ----------
    audio_path : str | Path
        Path to the audio file.
    model : Any
        Loaded Whisper model.
    config : WhisperConfig
        ASR configuration.

    Returns
    -------
    tuple[list[SegmentDict], TranscriptionMetrics]
    """
    audio_path = Path(audio_path)
    metrics = TranscriptionMetrics(
        file_name=audio_path.name,
        backend_used=config.backend,
    )

    # Probe audio duration without loading the waveform
    try:
        import librosa
        metrics.audio_duration = librosa.get_duration(path=str(audio_path))
    except Exception:  # noqa: BLE001
        metrics.audio_duration = 0.0

    t_start = time.perf_counter()
    try:
        segments = transcribe_audio(audio_path, model, config)
        metrics.num_segments = len(segments)
    except Exception as exc:  # noqa: BLE001
        logger.error("Unhandled error in transcribe_with_metrics for '%s': %s", audio_path, exc)
        segments = []
        metrics.error = str(exc)
    finally:
        metrics.processing_time = time.perf_counter() - t_start

    return segments, metrics
