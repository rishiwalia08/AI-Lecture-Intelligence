"""
src/audio_processing/audio_normalizer.py
-----------------------------------------
Audio normalisation module for the Speech RAG system — Phase 1.

Converts any supported audio file to the Whisper-compatible format:
  - 16 kHz sample rate
  - Mono channel
  - 16-bit PCM WAV

Usage
-----
    from src.audio_processing.audio_normalizer import normalize_audio, normalize_dataset

    # Single file
    normalize_audio("data/raw_audio/lecture.mp3", "data/processed_audio/lecture.wav")

    # Batch — reads from metadata CSV
    normalize_dataset("data/dataset_metadata.csv", "data/processed_audio")
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

import librosa
import numpy as np
import pandas as pd
import soundfile as sf
import yaml
from pydub import AudioSegment
from tqdm import tqdm

from src.utils.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────
TARGET_SAMPLE_RATE: int = 16_000
TARGET_CHANNELS: int = 1          # mono
TARGET_FORMAT: str = ".wav"


# ──────────────────────────────────────────────────────────────
# Core normalisation function
# ──────────────────────────────────────────────────────────────
def normalize_audio(
    input_path: str | Path,
    output_path: str | Path,
    target_sr: int = TARGET_SAMPLE_RATE,
) -> bool:
    """
    Normalize a single audio file to Whisper-compatible format.

    Steps
    -----
    1. Load audio via librosa (handles MP3, FLAC, OGG, WAV …).
    2. Resample to ``target_sr`` if necessary.
    3. Convert to mono by averaging channels.
    4. Export as 16-bit PCM WAV using soundfile.

    Parameters
    ----------
    input_path : str | Path
        Path to the source audio file.
    output_path : str | Path
        Destination path (should end in ``.wav``).
    target_sr : int
        Target sample rate in Hz (default 16 000).

    Returns
    -------
    bool
        True on success, False on failure.
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        logger.error("Input file not found: '%s'", input_path)
        return False

    try:
        logger.debug("Loading '%s'", input_path)
        # librosa loads as float32, mono=True already handles channel reduction
        waveform, source_sr = librosa.load(str(input_path), sr=None, mono=True)

        # Resample if needed
        if source_sr != target_sr:
            logger.debug(
                "Resampling '%s': %d Hz → %d Hz", input_path.name, source_sr, target_sr
            )
            waveform = librosa.resample(
                waveform, orig_sr=source_sr, target_sr=target_sr
            )

        # Ensure float32 is in [-1, 1] before writing as PCM16
        waveform = np.clip(waveform, -1.0, 1.0)

        # Create output directory if required
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write as 16-bit PCM WAV
        sf.write(
            str(output_path),
            waveform,
            target_sr,
            subtype="PCM_16",
            format="WAV",
        )
        logger.debug("Saved normalised audio to '%s'", output_path)
        return True

    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to normalise '%s': %s", input_path, exc)
        return False


# ──────────────────────────────────────────────────────────────
# Batch processing
# ──────────────────────────────────────────────────────────────
def normalize_dataset(
    metadata_csv: str | Path,
    output_dir: str | Path,
    target_sr: int = TARGET_SAMPLE_RATE,
    overwrite: bool = False,
) -> pd.DataFrame:
    """
    Batch-normalise all audio files listed in a metadata CSV.

    Reads the CSV produced by :mod:`src.data_ingestion.load_datasets`,
    processes each file, and appends a ``processed_path`` column to the
    returned DataFrame. A ``normalisation_status`` column records the
    result for every row.

    Parameters
    ----------
    metadata_csv : str | Path
        Path to ``data/dataset_metadata.csv``.
    output_dir : str | Path
        Directory for processed WAV files.
    target_sr : int
        Target sample rate (default 16 000 Hz).
    overwrite : bool
        Re-process files that already exist in ``output_dir`` if True.

    Returns
    -------
    pd.DataFrame
        Metadata DataFrame augmented with ``processed_path`` and
        ``normalisation_status`` columns.
    """
    metadata_csv = Path(metadata_csv)
    output_dir = Path(output_dir)

    if not metadata_csv.exists():
        logger.error("Metadata CSV not found: '%s'", metadata_csv)
        raise FileNotFoundError(f"Metadata CSV not found: {metadata_csv}")

    df = pd.read_csv(metadata_csv)
    logger.info(
        "Starting batch normalisation: %d files → '%s'", len(df), output_dir
    )

    processed_paths: list[str] = []
    statuses: list[str] = []

    for _, row in tqdm(df.iterrows(), total=len(df), desc="Normalising", unit="file"):
        input_path = Path(row["audio_path"])
        # Preserve relative sub-structure inside output_dir
        # e.g. datasets/tedlium/talk/audio.wav → processed_audio/tedlium/talk/audio.wav
        try:
            relative = input_path.relative_to(input_path.anchor)
        except ValueError:
            relative = Path(input_path.name)

        # Use dataset sub-folder to avoid collisions
        output_path = output_dir / row.get("dataset_name", "unknown") / (
            input_path.stem + TARGET_FORMAT
        )

        if output_path.exists() and not overwrite:
            logger.debug("Skipping existing file: '%s'", output_path)
            processed_paths.append(str(output_path))
            statuses.append("skipped")
            continue

        success = normalize_audio(input_path, output_path, target_sr=target_sr)
        processed_paths.append(str(output_path) if success else "")
        statuses.append("success" if success else "failed")

    df["processed_path"] = processed_paths
    df["normalisation_status"] = statuses

    n_success = statuses.count("success")
    n_skipped = statuses.count("skipped")
    n_failed = statuses.count("failed")
    logger.info(
        "Batch normalisation complete. success=%d  skipped=%d  failed=%d",
        n_success,
        n_skipped,
        n_failed,
    )
    return df


# ──────────────────────────────────────────────────────────────
# Validation helpers
# ──────────────────────────────────────────────────────────────
def validate_audio_format(
    audio_path: str | Path,
    expected_sr: int = TARGET_SAMPLE_RATE,
    expected_channels: int = TARGET_CHANNELS,
) -> dict:
    """
    Check that an audio file meets the expected format requirements.

    Parameters
    ----------
    audio_path : str | Path
        Path to the WAV file to validate.
    expected_sr : int
        Expected sample rate (default 16 000).
    expected_channels : int
        Expected number of channels (default 1 = mono).

    Returns
    -------
    dict
        Keys: ``path``, ``sample_rate``, ``channels``, ``duration``,
        ``is_valid``, ``issues``.
    """
    audio_path = Path(audio_path)
    result: dict = {
        "path": str(audio_path),
        "sample_rate": None,
        "channels": None,
        "duration": None,
        "is_valid": False,
        "issues": [],
    }

    if not audio_path.exists():
        result["issues"].append("File not found")
        return result

    try:
        info = sf.info(str(audio_path))
        result["sample_rate"] = info.samplerate
        result["channels"] = info.channels
        result["duration"] = info.duration

        if info.samplerate != expected_sr:
            result["issues"].append(
                f"sample_rate={info.samplerate} (expected {expected_sr})"
            )
        if info.channels != expected_channels:
            result["issues"].append(
                f"channels={info.channels} (expected {expected_channels})"
            )

        result["is_valid"] = len(result["issues"]) == 0
    except Exception as exc:  # noqa: BLE001
        result["issues"].append(str(exc))

    return result
