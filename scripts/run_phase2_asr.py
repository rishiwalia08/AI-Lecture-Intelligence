"""
scripts/run_phase2_asr.py
--------------------------
Phase 2 entrypoint: Whisper ASR transcription pipeline.

Reads Phase 1 metadata, transcribes each processed audio file, saves
full transcripts + per-segment files, and records per-file metrics.

Usage
-----
    python scripts/run_phase2_asr.py [--config config/config.yaml]
                                     [--backend openai|faster]
                                     [--limit N]
                                     [--dry-run]

Steps
-----
1. Load dataset_metadata.csv (Phase 1 output).
2. Filter rows with successfully normalised audio.
3. Load Whisper model once.
4. Iterate with progress bar → transcribe → validate → save.
5. Append metrics to logs/asr_metrics.csv.
6. Print summary: files processed / failed / total audio duration.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import List, Optional

import pandas as pd
import yaml
from tqdm import tqdm

# Ensure project root is importable when run directly
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.asr.whisper_transcriber import (
    WhisperConfig,
    TranscriptionMetrics,
    load_whisper_model,
    transcribe_with_metrics,
)
from src.asr.timestamp_formatter import (
    format_transcript,
    save_full_transcript,
    save_segments,
    validate_transcript,
)
from src.utils.logger import get_logger

logger = get_logger(__name__, log_file=_PROJECT_ROOT / "logs" / "asr_pipeline.log")


# ──────────────────────────────────────────────────────────────
# CLI argument parser
# ──────────────────────────────────────────────────────────────
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Speech RAG — Phase 2: Whisper ASR Transcription Pipeline"
    )
    parser.add_argument(
        "--config",
        default="config/config.yaml",
        help="Path to config YAML (default: config/config.yaml).",
    )
    parser.add_argument(
        "--backend",
        choices=["openai", "faster"],
        default=None,
        help="Force ASR backend. Overrides config value.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process only the first N audio files (useful for testing).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load metadata and model, but do not transcribe or write files.",
    )
    return parser.parse_args()


# ──────────────────────────────────────────────────────────────
# Config helpers
# ──────────────────────────────────────────────────────────────
def _load_config(config_path: Path) -> dict:
    with config_path.open() as fh:
        return yaml.safe_load(fh)


def _build_whisper_config(cfg: dict, backend_override: Optional[str]) -> WhisperConfig:
    return WhisperConfig(
        model_size=cfg.get("asr_model_size", "large-v3"),
        device=cfg.get("device", "cuda"),
        backend=backend_override or cfg.get("asr_backend", "openai"),
        batch_size=cfg.get("batch_size", 4),
        language=cfg.get("asr_language", "en"),
    )


# ──────────────────────────────────────────────────────────────
# Metrics CSV
# ──────────────────────────────────────────────────────────────
_METRICS_COLUMNS = [
    "file_name",
    "audio_duration",
    "processing_time",
    "num_segments",
    "backend_used",
    "realtime_factor",
    "error",
]


def _init_metrics_csv(metrics_path: Path) -> None:
    """Create the metrics CSV with headers if it doesn't already exist."""
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    if not metrics_path.exists():
        with metrics_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_METRICS_COLUMNS)
            writer.writeheader()


def _append_metrics_row(metrics_path: Path, metrics: TranscriptionMetrics) -> None:
    """Append a single metrics row to the CSV."""
    with metrics_path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_METRICS_COLUMNS)
        writer.writerow(metrics.to_dict())


# ──────────────────────────────────────────────────────────────
# Pipeline steps
# ──────────────────────────────────────────────────────────────
def _load_audio_files(
    cfg: dict,
    project_root: Path,
    limit: Optional[int],
) -> pd.DataFrame:
    """
    Read Phase 1 metadata CSV and return rows ready for transcription.

    Priority order for audio path:
    1. ``processed_path`` column (Phase 1 normalised WAV)
    2. ``audio_path`` column (original)
    """
    metadata_csv = project_root / cfg.get("metadata_output_path", "data/dataset_metadata.csv")
    logger.info("Loading metadata from '%s'", metadata_csv)

    if not metadata_csv.exists():
        logger.warning(
            "Metadata CSV not found at '%s'. Creating an empty frame.", metadata_csv
        )
        return pd.DataFrame(columns=["audio_path", "dataset_name"])

    df = pd.read_csv(metadata_csv)

    # Prefer processed (normalised) paths when available
    if "processed_path" in df.columns:
        df["_target_path"] = df["processed_path"].where(
            df["processed_path"].notna() & (df["processed_path"] != ""),
            df["audio_path"],
        )
    else:
        df["_target_path"] = df["audio_path"]

    # Drop rows with no usable path
    df = df[df["_target_path"].notna() & (df["_target_path"] != "")]
    logger.info("%d audio files queued for transcription.", len(df))

    if limit:
        df = df.head(limit)
        logger.info("--limit %d: processing first %d files.", limit, len(df))

    return df


def _derive_lecture_id(row: pd.Series, idx: int) -> str:
    """
    Build a stable lecture_id from the audio filename.

    Falls back to a zero-padded index if the filename is not informative.
    """
    path = Path(str(row.get("_target_path", "")))
    stem = path.stem
    return stem if stem else f"lecture_{idx:04d}"


def _process_one(
    audio_path: Path,
    lecture_id: str,
    model: object,
    whisper_cfg: WhisperConfig,
    transcripts_dir: Path,
    segments_dir: Path,
    metrics_path: Path,
    dry_run: bool,
) -> bool:
    """
    Transcribe a single audio file, validate, and save outputs.

    Returns True on success, False on any failure.
    """
    if dry_run:
        logger.info("[DRY-RUN] Would transcribe '%s'.", audio_path)
        dummy_metrics = TranscriptionMetrics(
            file_name=audio_path.name,
            backend_used=whisper_cfg.backend,
        )
        _append_metrics_row(metrics_path, dummy_metrics)
        return True

    # ── Transcribe ────────────────────────────────────────────
    segments, metrics = transcribe_with_metrics(audio_path, model, whisper_cfg)
    _append_metrics_row(metrics_path, metrics)

    if metrics.error:
        logger.error("Error transcribing '%s': %s", audio_path, metrics.error)
        return False

    if not segments:
        logger.warning("No segments returned for '%s'. Skipping.", audio_path)
        return False

    # ── Format ────────────────────────────────────────────────
    transcript = format_transcript(
        lecture_id=lecture_id,
        segments=segments,
        metadata={"audio_path": str(audio_path)},
    )

    # ── Validate ──────────────────────────────────────────────
    validation = validate_transcript(transcript)
    if not validation.is_valid:
        logger.warning(
            "Transcript for '%s' failed validation: %s",
            lecture_id,
            "; ".join(validation.issues),
        )

    # ── Save ──────────────────────────────────────────────────
    save_full_transcript(transcript, transcripts_dir)
    save_segments(transcript, segments_dir)

    logger.info(
        "Done '%s': %d segs | %.1fs audio | %.1fs processing",
        lecture_id,
        metrics.num_segments,
        metrics.audio_duration,
        metrics.processing_time,
    )
    return True


# ──────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────
def _print_summary(
    n_success: int,
    n_failed: int,
    total_duration: float,
    elapsed: float,
) -> None:
    hours, rem = divmod(int(total_duration), 3600)
    minutes, seconds = divmod(rem, 60)
    lines = [
        "",
        "╔══════════════════════════════════════════════╗",
        "║       PHASE 2 ASR PIPELINE — SUMMARY         ║",
        "╠══════════════════════════════════════════════╣",
        f"║  Files succeeded  : {n_success:<25d}║",
        f"║  Files failed     : {n_failed:<25d}║",
        f"║  Total audio      : {hours:02d}h {minutes:02d}m {seconds:02d}s{'':<17}║",
        f"║  Elapsed time     : {elapsed:.1f}s{'':<22}║",
        "╚══════════════════════════════════════════════╝",
        "",
    ]
    for line in lines:
        logger.info(line)


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────
def main() -> None:
    args = _parse_args()
    start_time = time.time()

    project_root = _PROJECT_ROOT
    config_path = project_root / args.config

    if not config_path.exists():
        logger.error("Config file not found: '%s'", config_path)
        sys.exit(1)

    cfg = _load_config(config_path)
    whisper_cfg = _build_whisper_config(cfg, backend_override=args.backend)

    transcripts_dir = project_root / cfg.get("transcripts_path", "data/transcripts")
    segments_dir    = project_root / cfg.get("segments_path", "data/segments")
    metrics_path    = project_root / cfg.get("asr_metrics_path", "logs/asr_metrics.csv")

    transcripts_dir.mkdir(parents=True, exist_ok=True)
    segments_dir.mkdir(parents=True, exist_ok=True)
    _init_metrics_csv(metrics_path)

    logger.info(
        "Phase 2 ASR pipeline started. backend=%s  device=%s  dry_run=%s",
        whisper_cfg.backend,
        whisper_cfg.effective_device(),
        args.dry_run,
    )

    # ── Load Model ────────────────────────────────────────────
    model = None
    if not args.dry_run:
        try:
            model = load_whisper_model(whisper_cfg)
        except Exception as exc:
            logger.error("Failed to load Whisper model: %s", exc)
            sys.exit(1)

    # ── Load audio file list ──────────────────────────────────
    df = _load_audio_files(cfg, project_root, limit=args.limit)

    # ── Process files ─────────────────────────────────────────
    n_success = 0
    n_failed = 0
    total_audio_duration = df.get("duration", pd.Series(dtype=float)).sum()

    for idx, row in tqdm(
        df.iterrows(),
        total=len(df),
        desc="Transcribing",
        unit="file",
    ):
        audio_path = Path(str(row["_target_path"]))
        lecture_id = _derive_lecture_id(row, idx)

        ok = _process_one(
            audio_path=audio_path,
            lecture_id=lecture_id,
            model=model,
            whisper_cfg=whisper_cfg,
            transcripts_dir=transcripts_dir,
            segments_dir=segments_dir,
            metrics_path=metrics_path,
            dry_run=args.dry_run,
        )

        if ok:
            n_success += 1
        else:
            n_failed += 1

    elapsed = time.time() - start_time
    _print_summary(n_success, n_failed, total_audio_duration, elapsed)
    logger.info("Phase 2 ASR pipeline finished in %.1f seconds.", elapsed)


if __name__ == "__main__":
    main()
