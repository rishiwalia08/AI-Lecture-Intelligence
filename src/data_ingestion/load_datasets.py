"""
src/data_ingestion/load_datasets.py
------------------------------------
Data ingestion module for the Speech RAG system — Phase 1.

Loads audio metadata from four sources:
  - TED-LIUM Release 3
  - LibriSpeech
  - Common Voice (Indian English)
  - Local lecture recordings

All loaders return a pandas DataFrame with standardised columns and
optionally persist a combined CSV to ``data/dataset_metadata.csv``.

Usage
-----
    from src.data_ingestion.load_datasets import DataIngestionPipeline

    pipeline = DataIngestionPipeline(config_path="config/config.yaml")
    df = pipeline.run()
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import List, Optional

import librosa
import pandas as pd
import yaml
from tqdm import tqdm

from src.utils.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────
METADATA_COLUMNS: List[str] = [
    "audio_path",
    "dataset_name",
    "duration",
    "speaker_id",
    "sample_rate",
]

SUPPORTED_EXTENSIONS = {".wav", ".flac", ".mp3", ".ogg", ".m4a"}


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def _probe_audio(path: Path) -> tuple[float, int]:
    """
    Return ``(duration_seconds, sample_rate)`` for an audio file.

    Uses librosa's lazy-load to avoid reading the full waveform.
    Falls back to ``(0.0, 0)`` on failure.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            duration = librosa.get_duration(path=str(path))
            sr = librosa.get_samplerate(str(path))
        return float(duration), int(sr)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not probe audio '%s': %s", path, exc)
        return 0.0, 0


def _load_config(config_path: str | Path) -> dict:
    """Load YAML config and return as dict."""
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with config_path.open() as fh:
        return yaml.safe_load(fh)


# ──────────────────────────────────────────────────────────────
# Individual dataset loaders
# ──────────────────────────────────────────────────────────────
def load_tedlium_dataset(dataset_dir: str | Path) -> pd.DataFrame:
    """
    Load TED-LIUM Release 3 metadata.

    Expected layout::

        datasets/tedlium/
          <talk_id>/
            <talk_id>.sph  |  <talk_id>.wav
            <talk_id>.stm   (optional transcript)

    Parameters
    ----------
    dataset_dir : str | Path
        Root directory of the TED-LIUM dataset.

    Returns
    -------
    pd.DataFrame
        Rows matching ``METADATA_COLUMNS``.
    """
    dataset_dir = Path(dataset_dir)
    logger.info("Loading TED-LIUM dataset from '%s'", dataset_dir)

    if not dataset_dir.exists():
        logger.warning("TED-LIUM directory does not exist: %s", dataset_dir)
        return _empty_dataframe()

    records: list[dict] = []
    audio_files = [
        f for ext in SUPPORTED_EXTENSIONS
        for f in dataset_dir.rglob(f"*{ext}")
    ]

    for audio_path in tqdm(audio_files, desc="TED-LIUM", unit="file"):
        duration, sr = _probe_audio(audio_path)
        # Speaker ID is inferred from the parent folder name
        speaker_id = audio_path.parent.name
        records.append({
            "audio_path":   str(audio_path.resolve()),
            "dataset_name": "tedlium",
            "duration":     duration,
            "speaker_id":   speaker_id,
            "sample_rate":  sr,
        })

    df = pd.DataFrame(records, columns=METADATA_COLUMNS)
    logger.info("TED-LIUM: loaded %d records.", len(df))
    return df


def load_librispeech_dataset(dataset_dir: str | Path) -> pd.DataFrame:
    """
    Load LibriSpeech metadata.

    Expected layout (standard LibriSpeech)::

        datasets/librispeech/
          <speaker_id>/
            <chapter_id>/
              <utterance>.flac
              <speaker_id>-<chapter_id>.trans.txt  (optional)

    Parameters
    ----------
    dataset_dir : str | Path
        Root directory of the LibriSpeech dataset.

    Returns
    -------
    pd.DataFrame
        Rows matching ``METADATA_COLUMNS``.
    """
    dataset_dir = Path(dataset_dir)
    logger.info("Loading LibriSpeech dataset from '%s'", dataset_dir)

    if not dataset_dir.exists():
        logger.warning("LibriSpeech directory does not exist: %s", dataset_dir)
        return _empty_dataframe()

    records: list[dict] = []
    audio_files = list(dataset_dir.rglob("*.flac")) + list(
        dataset_dir.rglob("*.wav")
    )

    for audio_path in tqdm(audio_files, desc="LibriSpeech", unit="file"):
        duration, sr = _probe_audio(audio_path)
        # Standard LibriSpeech: speaker_id is the grandparent folder
        try:
            speaker_id = audio_path.parts[-3]
        except IndexError:
            speaker_id = "unknown"
        records.append({
            "audio_path":   str(audio_path.resolve()),
            "dataset_name": "librispeech",
            "duration":     duration,
            "speaker_id":   speaker_id,
            "sample_rate":  sr,
        })

    df = pd.DataFrame(records, columns=METADATA_COLUMNS)
    logger.info("LibriSpeech: loaded %d records.", len(df))
    return df


def load_commonvoice_dataset(
    dataset_dir: str | Path,
    tsv_filename: str = "train.tsv",
) -> pd.DataFrame:
    """
    Load Mozilla Common Voice (Indian English) metadata.

    The Common Voice dataset ships with TSV manifests. If a TSV is
    found, speaker IDs and paths are read from it. Otherwise the
    directory is scanned for audio files.

    Parameters
    ----------
    dataset_dir : str | Path
        Root directory of the Common Voice dataset.
    tsv_filename : str
        Name of the manifest TSV (default ``train.tsv``).

    Returns
    -------
    pd.DataFrame
        Rows matching ``METADATA_COLUMNS``.
    """
    dataset_dir = Path(dataset_dir)
    logger.info("Loading Common Voice dataset from '%s'", dataset_dir)

    if not dataset_dir.exists():
        logger.warning("Common Voice directory does not exist: %s", dataset_dir)
        return _empty_dataframe()

    tsv_path = dataset_dir / tsv_filename
    records: list[dict] = []

    if tsv_path.exists():
        logger.info("Found TSV manifest: %s", tsv_path)
        manifest = pd.read_csv(tsv_path, sep="\t")
        clips_dir = dataset_dir / "clips"

        for _, row in tqdm(
            manifest.iterrows(),
            total=len(manifest),
            desc="CommonVoice",
            unit="file",
        ):
            audio_path = clips_dir / row.get("path", "")
            if not audio_path.exists():
                logger.debug("Clip not found: %s", audio_path)
                continue
            duration, sr = _probe_audio(audio_path)
            records.append({
                "audio_path":   str(audio_path.resolve()),
                "dataset_name": "commonvoice_indian",
                "duration":     duration,
                "speaker_id":   str(row.get("client_id", "unknown")),
                "sample_rate":  sr,
            })
    else:
        # Fallback: scan directory
        logger.info("No TSV manifest found; scanning directory.")
        audio_files = [
            f for ext in SUPPORTED_EXTENSIONS
            for f in dataset_dir.rglob(f"*{ext}")
        ]
        for audio_path in tqdm(audio_files, desc="CommonVoice", unit="file"):
            duration, sr = _probe_audio(audio_path)
            records.append({
                "audio_path":   str(audio_path.resolve()),
                "dataset_name": "commonvoice_indian",
                "duration":     duration,
                "speaker_id":   "unknown",
                "sample_rate":  sr,
            })

    df = pd.DataFrame(records, columns=METADATA_COLUMNS)
    logger.info("Common Voice: loaded %d records.", len(df))
    return df


def load_local_lectures(lectures_dir: str | Path) -> pd.DataFrame:
    """
    Load local lecture recordings from a flat or nested directory.

    Parameters
    ----------
    lectures_dir : str | Path
        Directory containing raw lecture audio files.

    Returns
    -------
    pd.DataFrame
        Rows matching ``METADATA_COLUMNS``.
    """
    lectures_dir = Path(lectures_dir)
    logger.info("Loading local lectures from '%s'", lectures_dir)

    if not lectures_dir.exists():
        logger.warning("Local lectures directory does not exist: %s", lectures_dir)
        return _empty_dataframe()

    records: list[dict] = []
    audio_files = [
        f for ext in SUPPORTED_EXTENSIONS
        for f in lectures_dir.rglob(f"*{ext}")
    ]

    for audio_path in tqdm(audio_files, desc="Local Lectures", unit="file"):
        duration, sr = _probe_audio(audio_path)
        records.append({
            "audio_path":   str(audio_path.resolve()),
            "dataset_name": "local_lectures",
            "duration":     duration,
            "speaker_id":   audio_path.parent.name,  # folder as speaker
            "sample_rate":  sr,
        })

    df = pd.DataFrame(records, columns=METADATA_COLUMNS)
    logger.info("Local lectures: loaded %d records.", len(df))
    return df


# ──────────────────────────────────────────────────────────────
# Pipeline orchestrator
# ──────────────────────────────────────────────────────────────
class DataIngestionPipeline:
    """
    Orchestrate loading of all configured datasets.

    Parameters
    ----------
    config_path : str | Path
        Path to ``config/config.yaml``.
    project_root : str | Path, optional
        Project root used to resolve relative paths in config.
        Defaults to the directory two levels above this file.
    """

    def __init__(
        self,
        config_path: str | Path = "config/config.yaml",
        project_root: Optional[str | Path] = None,
    ) -> None:
        self.config = _load_config(config_path)
        self.project_root = Path(project_root or Path(__file__).parents[3])
        logger.info("DataIngestionPipeline initialised. Root: %s", self.project_root)

    def _abs(self, rel: str) -> Path:
        """Resolve a config-relative path against the project root."""
        return self.project_root / rel

    def run(self, save: bool = True) -> pd.DataFrame:
        """
        Load all datasets and return a combined DataFrame.

        Parameters
        ----------
        save : bool
            Persist the combined metadata CSV if True (default).

        Returns
        -------
        pd.DataFrame
        """
        paths = self.config.get("dataset_paths", {})

        frames = [
            load_tedlium_dataset(self._abs(paths.get("tedlium", "datasets/tedlium"))),
            load_librispeech_dataset(self._abs(paths.get("librispeech", "datasets/librispeech"))),
            load_commonvoice_dataset(self._abs(paths.get("commonvoice", "datasets/commonvoice_indian"))),
            load_local_lectures(self._abs(paths.get("local_lectures", "data/raw_audio"))),
        ]

        combined = pd.concat(frames, ignore_index=True)
        logger.info("Total records loaded: %d", len(combined))

        if save:
            self._save_metadata(combined)

        return combined

    def _save_metadata(self, df: pd.DataFrame) -> None:
        """Write the metadata DataFrame to CSV."""
        out_path = self._abs(
            self.config.get("metadata_output_path", "data/dataset_metadata.csv")
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
        logger.info("Metadata saved to '%s' (%d rows).", out_path, len(df))


# ──────────────────────────────────────────────────────────────
# Utilities
# ──────────────────────────────────────────────────────────────
def _empty_dataframe() -> pd.DataFrame:
    """Return an empty DataFrame with the standard schema."""
    return pd.DataFrame(columns=METADATA_COLUMNS)
