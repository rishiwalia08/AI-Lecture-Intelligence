"""
src/asr/timestamp_formatter.py
--------------------------------
Segment formatting, JSON I/O, and validation for the Speech RAG Phase 2 ASR
pipeline.

Responsibilities
----------------
- Build the canonical transcript JSON structure from raw segments.
- Write full-transcript JSON to ``data/transcripts/``.
- Write per-segment JSON to ``data/segments/``.
- Validate transcript integrity (ordering, non-empty text, field presence).
- Round-trip load of saved transcripts.

Usage
-----
    from src.asr.timestamp_formatter import (
        format_transcript, save_full_transcript,
        save_segments, validate_transcript,
    )

    segments = [{"text": "Hello world", "start": 0.0, "end": 2.5}]
    transcript = format_transcript("lecture_01", segments)
    save_full_transcript(transcript, output_dir="data/transcripts")
    save_segments(transcript, segments_dir="data/segments")
    result = validate_transcript(transcript)
    print(result.is_valid, result.issues)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────
# Type aliases
# ──────────────────────────────────────────────────────────────
SegmentDict  = Dict[str, Any]    # {"text": str, "start": float, "end": float}
TranscriptDict = Dict[str, Any]  # {"lecture_id": str, "segments": [...], ...}


# ──────────────────────────────────────────────────────────────
# Validation result
# ──────────────────────────────────────────────────────────────
@dataclass
class ValidationResult:
    """
    Result of :func:`validate_transcript`.

    Attributes
    ----------
    is_valid : bool
        True only when zero issues were found.
    issues : list[str]
        Human-readable descriptions of each problem.
    num_segments : int
        Total segments examined.
    num_empty : int
        Segments with empty or whitespace-only text.
    num_ordering_errors : int
        Segments where ``start`` > previous ``end``.
    """

    is_valid: bool = True
    issues: List[str] = field(default_factory=list)
    num_segments: int = 0
    num_empty: int = 0
    num_ordering_errors: int = 0

    def add_issue(self, msg: str) -> None:
        self.is_valid = False
        self.issues.append(msg)


# ──────────────────────────────────────────────────────────────
# Formatting
# ──────────────────────────────────────────────────────────────
def format_transcript(
    lecture_id: str,
    segments: List[SegmentDict],
    metadata: Optional[Dict[str, Any]] = None,
) -> TranscriptDict:
    """
    Build the canonical transcript dictionary from raw ASR segments.

    Parameters
    ----------
    lecture_id : str
        Unique lecture identifier (e.g. ``"lecture_01"``).
    segments : list of dict
        Raw segment list: ``[{"text": str, "start": float, "end": float}]``.
    metadata : dict, optional
        Optional extra fields merged into the transcript root
        (e.g. ``{"dataset_name": "local_lectures", "audio_path": "..."}``).

    Returns
    -------
    dict
        Structure::

            {
                "lecture_id": "lecture_01",
                "num_segments": 42,
                "total_duration": 1823.4,
                "segments": [
                    {"segment_id": "001", "text": "...", "start": 0.0, "end": 3.2},
                    ...
                ],
                ...metadata fields...
            }
    """
    normalised: List[SegmentDict] = []
    for idx, seg in enumerate(segments):
        normalised.append({
            "segment_id": f"{idx + 1:03d}",
            "text":       seg.get("text", "").strip(),
            "start":      round(float(seg.get("start", 0.0)), 3),
            "end":        round(float(seg.get("end", 0.0)), 3),
        })

    total_duration = normalised[-1]["end"] if normalised else 0.0

    transcript: TranscriptDict = {
        "lecture_id":     lecture_id,
        "num_segments":   len(normalised),
        "total_duration": round(total_duration, 3),
        "segments":       normalised,
    }
    if metadata:
        transcript.update(metadata)

    return transcript


def format_segment_file(
    lecture_id: str,
    segment: SegmentDict,
) -> Dict[str, Any]:
    """
    Wrap a single segment into the per-segment JSON structure.

    Parameters
    ----------
    lecture_id : str
        Parent lecture identifier.
    segment : dict
        A normalised segment dict (from :func:`format_transcript`).

    Returns
    -------
    dict
    """
    return {
        "lecture_id":  lecture_id,
        "segment_id":  segment["segment_id"],
        "text":        segment["text"],
        "start":       segment["start"],
        "end":         segment["end"],
    }


# ──────────────────────────────────────────────────────────────
# I/O helpers
# ──────────────────────────────────────────────────────────────
def save_full_transcript(
    transcript: TranscriptDict,
    output_dir: str | Path,
) -> Path:
    """
    Write the full transcript to ``<output_dir>/<lecture_id>_transcript.json``.

    Parameters
    ----------
    transcript : dict
        Output of :func:`format_transcript`.
    output_dir : str | Path
        Destination directory (created if absent).

    Returns
    -------
    Path
        The written file path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    lecture_id = transcript.get("lecture_id", "unknown")
    out_path = output_dir / f"{lecture_id}_transcript.json"

    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(transcript, fh, ensure_ascii=False, indent=2)

    logger.info(
        "Full transcript saved: '%s' (%d segments).",
        out_path,
        transcript.get("num_segments", 0),
    )
    return out_path


def save_segments(
    transcript: TranscriptDict,
    segments_dir: str | Path,
) -> List[Path]:
    """
    Write one JSON file per segment to ``<segments_dir>``.

    File naming convention::

        <lecture_id>_segment_<NNN>.json   (zero-padded 3-digit index)

    Parameters
    ----------
    transcript : dict
        Output of :func:`format_transcript`.
    segments_dir : str | Path
        Destination directory (created if absent).

    Returns
    -------
    list of Path
        Paths of all written segment files.
    """
    segments_dir = Path(segments_dir)
    lecture_id   = transcript.get("lecture_id", "unknown")
    lec_dir      = segments_dir / lecture_id
    lec_dir.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []
    for seg in transcript.get("segments", []):
        filename = f"{lecture_id}_segment_{seg['segment_id']}.json"
        out_path = lec_dir / filename
        payload  = format_segment_file(lecture_id, seg)
        with out_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        written.append(out_path)

    logger.info(
        "Saved %d segment files for '%s' → '%s'.",
        len(written), lecture_id, lec_dir,
    )
    return written


def load_transcript(path: str | Path) -> TranscriptDict:
    """
    Load a saved full-transcript JSON from disk.

    Parameters
    ----------
    path : str | Path
        Path to the ``*_transcript.json`` file.

    Returns
    -------
    dict
        The transcript dictionary.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    json.JSONDecodeError
        If the file is malformed.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Transcript not found: {path}")
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    logger.debug("Loaded transcript '%s' (%d segments).", path.name, len(data.get("segments", [])))
    return data


# ──────────────────────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────────────────────
def validate_transcript(transcript: TranscriptDict) -> ValidationResult:
    """
    Validate a transcript dictionary for downstream usability.

    Checks performed
    ----------------
    1. ``lecture_id`` is present and non-empty.
    2. ``segments`` key exists and is a list.
    3. Each segment has ``text``, ``start``, ``end`` keys.
    4. No segment has empty ``text``.
    5. Segment timestamps are ordered (``start``\\ i ≤ ``end``\\ i,
       ``start``\\ i+1 ≥ ``start``\\ i).

    Parameters
    ----------
    transcript : dict
        Output of :func:`format_transcript`.

    Returns
    -------
    ValidationResult
    """
    result = ValidationResult()

    # ── Top-level fields ──────────────────────────────────────
    if not transcript.get("lecture_id", "").strip():
        result.add_issue("Missing or empty 'lecture_id'.")

    segments = transcript.get("segments")
    if not isinstance(segments, list):
        result.add_issue("'segments' key is missing or not a list.")
        return result

    result.num_segments = len(segments)

    if result.num_segments == 0:
        result.add_issue("Transcript has zero segments.")
        return result

    # ── Per-segment checks ────────────────────────────────────
    prev_start: Optional[float] = None

    for idx, seg in enumerate(segments):
        label = f"Segment {idx + 1}"

        # Required keys
        for key in ("text", "start", "end"):
            if key not in seg:
                result.add_issue(f"{label}: missing field '{key}'.")

        # Empty text
        if not str(seg.get("text", "")).strip():
            result.num_empty += 1
            result.add_issue(f"{label}: empty text.")

        # start ≤ end
        start = seg.get("start", 0.0)
        end   = seg.get("end", 0.0)
        if start > end:
            result.num_ordering_errors += 1
            result.add_issue(
                f"{label}: start ({start}) > end ({end})."
            )

        # Monotonic ordering
        if prev_start is not None and start < prev_start:
            result.num_ordering_errors += 1
            result.add_issue(
                f"{label}: start ({start}) is before previous start ({prev_start}) — not monotonic."
            )

        prev_start = start

    if result.is_valid:
        logger.info(
            "Transcript '%s' is valid (%d segments).",
            transcript.get("lecture_id"), result.num_segments,
        )
    else:
        logger.warning(
            "Transcript '%s' has %d issue(s): %s",
            transcript.get("lecture_id"),
            len(result.issues),
            "; ".join(result.issues),
        )

    return result
