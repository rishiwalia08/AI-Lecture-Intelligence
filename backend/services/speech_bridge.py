"""
backend/services/speech_bridge.py
------------------------------------
Audio upload handling and Whisper transcription for the API layer.

Saves uploaded audio bytes to a temporary file, runs Whisper transcription,
and cleans up automatically via a context manager.

Usage
-----
    from backend.services.speech_bridge import transcribe_upload

    # In a FastAPI route:
    text = await transcribe_upload(file)   # file: UploadFile
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from src.utils.logger import get_logger

logger = get_logger(__name__)

_TMP_DIR = Path(__file__).resolve().parents[2] / "tmp"
_TMP_DIR.mkdir(exist_ok=True)

# Whisper model size for query transcription — "base" is fast and accurate enough
_WHISPER_MODEL_SIZE = "base"


@asynccontextmanager
async def _tmp_audio_file(data: bytes, suffix: str = ".wav") -> AsyncIterator[Path]:
    """
    Async context manager: write bytes to a temp file, yield its path,
    then delete it on exit.
    """
    path = _TMP_DIR / f"audio_{uuid.uuid4().hex}{suffix}"
    try:
        path.write_bytes(data)
        yield path
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass


async def transcribe_upload(
    audio_data: bytes,
    filename:   str = "audio.wav",
) -> str:
    """
    Transcribe raw audio bytes using OpenAI Whisper.

    Parameters
    ----------
    audio_data : bytes
        Raw bytes from the uploaded audio file.
    filename : str
        Original filename — used to infer the file extension.

    Returns
    -------
    str
        Transcribed text.

    Raises
    ------
    ImportError  If openai-whisper is not installed.
    RuntimeError If transcription produces no output.
    """
    suffix = Path(filename).suffix or ".wav"
    t0     = time.perf_counter()

    try:
        import whisper  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "openai-whisper is not installed. Run: pip install openai-whisper"
        ) from exc

    async with _tmp_audio_file(audio_data, suffix=suffix) as audio_path:
        logger.info("Transcribing audio file '%s' (%d bytes).", audio_path.name, len(audio_data))
        model  = whisper.load_model(_WHISPER_MODEL_SIZE)
        result = model.transcribe(str(audio_path))

    text = (result.get("text") or "").strip()
    logger.info(
        "Transcription complete in %.1fs: '%s'",
        time.perf_counter() - t0, text[:80],
    )

    if not text:
        raise RuntimeError("Whisper transcription returned empty text.")

    return text
