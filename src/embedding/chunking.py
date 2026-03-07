"""
src/embedding/chunking.py
--------------------------
Transcript chunking module for the Speech RAG system — Phase 3.

Converts Whisper transcript segments into fixed-size, overlapping text
chunks annotated with their source timestamps. Each chunk carries enough
metadata for ChromaDB storage and downstream retrieval.

Strategy
--------
- Concatenate all segment texts (preserving segment boundaries).
- Slide a token window of ``chunk_size`` tokens with ``chunk_overlap``
  overlap across the concatenated token stream.
- Each chunk records which segments it spans so ``start_time`` and
  ``end_time`` are exact.

Token counting uses whitespace splitting — lightweight, no external
tokenizer required, and easily swappable for a BPE tokenizer later.

Usage
-----
    from src.embedding.chunking import ChunkConfig, create_chunks, save_chunks

    config = ChunkConfig(chunk_size=500, chunk_overlap=50)
    chunks = create_chunks(transcript_dict, config)
    save_chunks(chunks, output_dir="data/chunks")
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────
@dataclass
class ChunkConfig:
    """
    Configuration for the chunking strategy.

    Attributes
    ----------
    chunk_size : int
        Maximum token count per chunk (whitespace-split tokens).
    chunk_overlap : int
        Number of tokens shared between consecutive chunks.
    min_chunk_tokens : int
        Discard chunks shorter than this (avoids stub chunks at the end).
    """
    chunk_size: int = 500
    chunk_overlap: int = 50
    min_chunk_tokens: int = 20

    def __post_init__(self) -> None:
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be less than "
                f"chunk_size ({self.chunk_size})."
            )


@dataclass
class Chunk:
    """
    A single searchable text chunk derived from a transcript.

    Attributes
    ----------
    chunk_id : str
        Globally unique identifier: ``<lecture_id>_chunk_<NNN>``.
    text : str
        The chunk text (joined tokens).
    start_time : float
        Start time (seconds) of the first covered segment.
    end_time : float
        End time (seconds) of the last covered segment.
    lecture_id : str
        Parent lecture identifier.
    segment_ids : list[str]
        IDs of the Whisper segments this chunk spans.
    chunk_index : int
        Zero-based position of this chunk within the lecture.
    token_count : int
        Number of whitespace tokens in ``text``.
    """
    chunk_id: str
    text: str
    start_time: float
    end_time: float
    lecture_id: str
    segment_ids: List[str]
    chunk_index: int
    token_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────
@dataclass
class _SegmentToken:
    """Associates a whitespace token with the segment it came from."""
    token: str
    segment_id: str
    start_time: float
    end_time: float


def _tokenise_segments(segments: List[Dict[str, Any]]) -> List[_SegmentToken]:
    """
    Flatten transcript segments into a list of per-token records.

    Each whitespace-split token is tagged with its parent segment's
    ``segment_id``, ``start_time``, and ``end_time``.
    """
    tokens: List[_SegmentToken] = []
    for seg in segments:
        seg_id = str(seg.get("segment_id", seg.get("id", "unknown")))
        start  = float(seg.get("start", 0.0))
        end    = float(seg.get("end", 0.0))
        text   = str(seg.get("text", "")).strip()
        for tok in text.split():
            tokens.append(_SegmentToken(
                token=tok,
                segment_id=seg_id,
                start_time=start,
                end_time=end,
            ))
    return tokens


# ──────────────────────────────────────────────────────────────
# Core API
# ──────────────────────────────────────────────────────────────
def create_chunks(
    transcript: Dict[str, Any],
    config: Optional[ChunkConfig] = None,
) -> List[Chunk]:
    """
    Convert a lecture transcript into overlapping text chunks.

    Parameters
    ----------
    transcript : dict
        Transcript dict as produced by Phase 2 ``format_transcript()``.
        Must contain ``"lecture_id"`` and ``"segments"`` keys.
    config : ChunkConfig, optional
        Chunking parameters. Defaults to ``ChunkConfig()``.

    Returns
    -------
    list[Chunk]
        Ordered list of chunks covering the full transcript.
    """
    config = config or ChunkConfig()
    lecture_id = transcript.get("lecture_id", "unknown")
    segments   = transcript.get("segments", [])

    if not segments:
        logger.warning("Transcript '%s' has no segments. Returning empty chunk list.", lecture_id)
        return []

    # Flatten segments → per-token records
    token_records = _tokenise_segments(segments)
    total_tokens  = len(token_records)

    if total_tokens == 0:
        logger.warning("Transcript '%s' has segments but zero tokens.", lecture_id)
        return []

    logger.info(
        "Chunking '%s': %d segments → %d tokens (size=%d, overlap=%d)",
        lecture_id, len(segments), total_tokens, config.chunk_size, config.chunk_overlap,
    )

    chunks: List[Chunk] = []
    step   = config.chunk_size - config.chunk_overlap
    start  = 0

    while start < total_tokens:
        end  = min(start + config.chunk_size, total_tokens)
        window = token_records[start:end]

        # Discard very short tail chunks
        if len(window) < config.min_chunk_tokens:
            logger.debug("Discarding short tail chunk (%d tokens) for '%s'.", len(window), lecture_id)
            break

        text = " ".join(t.token for t in window)

        # Collect unique segment IDs preserving order
        seen_segs: dict[str, None] = {}
        for t in window:
            seen_segs[t.segment_id] = None
        seg_ids = list(seen_segs.keys())

        chunk = Chunk(
            chunk_id    = f"{lecture_id}_chunk_{len(chunks) + 1:03d}",
            text        = text,
            start_time  = window[0].start_time,
            end_time    = window[-1].end_time,
            lecture_id  = lecture_id,
            segment_ids = seg_ids,
            chunk_index = len(chunks),
            token_count = len(window),
        )
        chunks.append(chunk)

        if end == total_tokens:
            break
        start += step

    logger.info("Created %d chunks for '%s'.", len(chunks), lecture_id)
    return chunks


# ──────────────────────────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────────────────────────
def save_chunks(
    chunks: List[Chunk],
    output_dir: str | Path,
) -> Path:
    """
    Persist a list of chunks to ``<output_dir>/<lecture_id>_chunks.json``.

    Parameters
    ----------
    chunks : list[Chunk]
        Chunks produced by :func:`create_chunks`.
    output_dir : str | Path
        Directory for chunk output (created if absent).

    Returns
    -------
    Path
        The written file path.
    """
    if not chunks:
        logger.warning("save_chunks: received empty chunk list — nothing written.")
        return Path(output_dir)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    lecture_id = chunks[0].lecture_id
    out_path   = output_dir / f"{lecture_id}_chunks.json"

    payload = {
        "lecture_id":  lecture_id,
        "num_chunks":  len(chunks),
        "chunks":      [c.to_dict() for c in chunks],
    }
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)

    logger.info("Saved %d chunks for '%s' → '%s'.", len(chunks), lecture_id, out_path)
    return out_path


def load_chunks(path: str | Path) -> List[Chunk]:
    """
    Load chunks from a previously saved JSON file.

    Parameters
    ----------
    path : str | Path
        Path to a ``*_chunks.json`` file.

    Returns
    -------
    list[Chunk]

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Chunk file not found: {path}")

    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    chunks = [Chunk(**c) for c in data.get("chunks", [])]
    logger.debug("Loaded %d chunks from '%s'.", len(chunks), path.name)
    return chunks
