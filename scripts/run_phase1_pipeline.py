"""
scripts/run_phase1_pipeline.py
-------------------------------
Phase 1 entrypoint for the Interactive Lecture Intelligence pipeline.

Steps
-----
1. Load dataset metadata from all configured sources.
2. Normalise audio to 16 kHz mono WAV.
3. Validate processed audio files.
4. Save enriched metadata CSV.

Usage
-----
    python scripts/run_phase1_pipeline.py [--config config/config.yaml]

Options
-------
--config   Path to config YAML (default: config/config.yaml).
--skip-normalization  Load and validate only (skip audio conversion).
--dry-run  Log what would happen without writing any files.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

# Ensure project root is on sys.path when run directly
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.data_ingestion.load_datasets import DataIngestionPipeline
from src.audio_processing.audio_normalizer import normalize_dataset, validate_audio_format
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Argument parser
# ──────────────────────────────────────────────────────────────
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Speech RAG — Phase 1: Data Ingestion & Preprocessing"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to config YAML file (default: config/config.yaml).",
    )
    parser.add_argument(
        "--skip-normalization",
        action="store_true",
        help="Skip audio normalisation step.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform all checks but do not write files.",
    )
    return parser.parse_args()


# ──────────────────────────────────────────────────────────────
# Pipeline steps
# ──────────────────────────────────────────────────────────────
def step1_load_metadata(
    config_path: str,
    project_root: Path,
    dry_run: bool,
) -> pd.DataFrame:
    """Load and optionally save dataset metadata."""
    logger.info("═" * 60)
    logger.info("STEP 1 — Loading dataset metadata")
    logger.info("═" * 60)

    pipeline = DataIngestionPipeline(config_path=config_path, project_root=project_root)
    df = pipeline.run(save=not dry_run)

    logger.info(
        "STEP 1 complete: %d total records loaded across %d datasets.",
        len(df),
        df["dataset_name"].nunique() if len(df) > 0 else 0,
    )
    return df


def step2_normalize_audio(
    df: pd.DataFrame,
    config: dict,
    project_root: Path,
    dry_run: bool,
) -> pd.DataFrame:
    """Batch-normalise all audio files."""
    logger.info("═" * 60)
    logger.info("STEP 2 — Normalising audio files")
    logger.info("═" * 60)

    if len(df) == 0:
        logger.warning("No records to normalise. Skipping.")
        return df

    if dry_run:
        logger.info("[DRY-RUN] Would normalise %d files.", len(df))
        df["processed_path"] = ""
        df["normalisation_status"] = "dry_run"
        return df

    # Save/use temp metadata CSV for normalize_dataset
    metadata_csv = project_root / config.get(
        "metadata_output_path", "data/dataset_metadata.csv"
    )
    output_dir = project_root / config.get(
        "processed_audio_path", "data/processed_audio"
    )

    if not metadata_csv.exists():
        logger.warning("metadata CSV not found; saving a temp copy.")
        metadata_csv.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(metadata_csv, index=False)

    df = normalize_dataset(
        metadata_csv=metadata_csv,
        output_dir=output_dir,
        target_sr=config.get("audio_sample_rate", 16000),
    )

    n_success = (df["normalisation_status"] == "success").sum()
    n_failed  = (df["normalisation_status"] == "failed").sum()
    n_skipped = (df["normalisation_status"] == "skipped").sum()
    logger.info(
        "STEP 2 complete: success=%d  failed=%d  skipped=%d",
        n_success, n_failed, n_skipped,
    )
    return df


def step3_validate_audio(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Validate that processed audio files meet format requirements."""
    logger.info("═" * 60)
    logger.info("STEP 3 — Validating processed audio")
    logger.info("═" * 60)

    if "processed_path" not in df.columns:
        logger.warning("No processed_path column. Skipping validation.")
        return df

    valid_rows = df[df["processed_path"].str.strip() != ""]
    results = []

    for _, row in valid_rows.iterrows():
        result = validate_audio_format(
            row["processed_path"],
            expected_sr=config.get("audio_sample_rate", 16000),
            expected_channels=config.get("audio_channels", 1),
        )
        results.append(result)

    if results:
        valid_count = sum(1 for r in results if r["is_valid"])
        invalid_count = len(results) - valid_count
        logger.info(
            "STEP 3 complete: %d valid  %d invalid (of %d validated).",
            valid_count, invalid_count, len(results),
        )
    else:
        logger.info("STEP 3: No processed files to validate.")

    return df


def step4_save_enriched_metadata(
    df: pd.DataFrame,
    config: dict,
    project_root: Path,
    dry_run: bool,
) -> None:
    """Persist the final enriched metadata."""
    logger.info("═" * 60)
    logger.info("STEP 4 — Saving enriched metadata")
    logger.info("═" * 60)

    if dry_run:
        logger.info("[DRY-RUN] Would save %d-row metadata CSV.", len(df))
        return

    out_path = project_root / config.get(
        "metadata_output_path", "data/dataset_metadata.csv"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    logger.info("STEP 4 complete: metadata saved to '%s'.", out_path)


# ──────────────────────────────────────────────────────────────
# Summary report
# ──────────────────────────────────────────────────────────────
def _print_summary(df: pd.DataFrame, elapsed: float) -> None:
    """Print a human-readable pipeline summary."""
    n_files = len(df)
    total_duration = df["duration"].sum() if "duration" in df.columns else 0.0
    n_errors = (
        (df["normalisation_status"] == "failed").sum()
        if "normalisation_status" in df.columns
        else 0
    )

    hours, rem = divmod(int(total_duration), 3600)
    minutes, seconds = divmod(rem, 60)

    summary_lines = [
        "",
        "╔══════════════════════════════════════════════╗",
        "║       PHASE 1 PIPELINE — SUMMARY             ║",
        "╠══════════════════════════════════════════════╣",
        f"║  Files processed  : {n_files:<25d}║",
        f"║  Total audio      : {hours:02d}h {minutes:02d}m {seconds:02d}s{'':<17}║",
        f"║  Errors           : {n_errors:<25d}║",
        f"║  Elapsed time     : {elapsed:.1f}s{'':<22}║",
        "╚══════════════════════════════════════════════╝",
        "",
    ]
    for line in summary_lines:
        logger.info(line)


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────
def main() -> None:
    args = _parse_args()
    start_time = time.time()

    project_root = _PROJECT_ROOT
    config_path = project_root / args.config

    logger.info("Starting Phase 1 pipeline. Config: '%s'", config_path)

    if not config_path.exists():
        logger.error("Config file not found: '%s'", config_path)
        sys.exit(1)

    with config_path.open() as fh:
        config = yaml.safe_load(fh)

    # ── Step 1: Load metadata ──────────────────────────────────
    df = step1_load_metadata(str(config_path), project_root, dry_run=args.dry_run)

    # ── Step 2: Normalize audio ────────────────────────────────
    if not args.skip_normalization:
        df = step2_normalize_audio(df, config, project_root, dry_run=args.dry_run)
    else:
        logger.info("STEP 2 — Skipped (--skip-normalization).")

    # ── Step 3: Validate audio ─────────────────────────────────
    df = step3_validate_audio(df, config)

    # ── Step 4: Save enriched metadata ────────────────────────
    step4_save_enriched_metadata(df, config, project_root, dry_run=args.dry_run)

    elapsed = time.time() - start_time
    _print_summary(df, elapsed)
    logger.info("Phase 1 pipeline finished in %.1f seconds.", elapsed)


if __name__ == "__main__":
    main()
