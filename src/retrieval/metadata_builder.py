"""
src/retrieval/metadata_builder.py
-----------------------------------
Metadata construction helpers for the Speech RAG system — Phase 3.

Builds ChromaDB-compatible metadata dicts from :class:`Chunk` objects and
formats search results into the canonical output schema.

Usage
-----
    from src.retrieval.metadata_builder import build_chunk_metadata, build_search_result

    meta   = build_chunk_metadata(chunk)
    result = build_search_result(doc_text, meta, distance=0.12)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Timestamp formatting
# ──────────────────────────────────────────────────────────────
def format_timestamp(seconds: float) -> str:
    """
    Convert a float seconds value to a ``"HH:MM:SS"`` or ``"MM:SS"``
    display string.

    Parameters
    ----------
    seconds : float
        Elapsed time in seconds.

    Returns
    -------
    str
        ``"MM:SS"`` for durations under one hour,
        ``"HH:MM:SS"`` for longer durations.

    Examples
    --------
    >>> format_timestamp(122.4)
    '02:02'
    >>> format_timestamp(3723.0)
    '01:02:03'
    """
    seconds = max(0.0, float(seconds))
    total_s = int(seconds)
    hours   = total_s // 3600
    minutes = (total_s % 3600) // 60
    secs    = total_s % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


# ──────────────────────────────────────────────────────────────
# Metadata builders
# ──────────────────────────────────────────────────────────────
def build_chunk_metadata(chunk: Any) -> Dict[str, Any]:
    """
    Build a ChromaDB-compatible metadata dict from a :class:`~src.embedding.chunking.Chunk`.

    ChromaDB only allows scalar values (str, int, float, bool) in metadata,
    so list fields (``segment_ids``) are serialised as
    pipe-delimited strings.

    Parameters
    ----------
    chunk : Chunk
        A chunk produced by :func:`~src.embedding.chunking.create_chunks`.

    Returns
    -------
    dict
        Flat metadata dict ready for ChromaDB insertion.
    """
    # segment_ids may be a list or already a string (if loaded from JSON)
    seg_ids = chunk.segment_ids
    if isinstance(seg_ids, list):
        seg_ids = "|".join(str(s) for s in seg_ids)

    return {
        "lecture_id":   str(chunk.lecture_id),
        "chunk_index":  int(chunk.chunk_index),
        "start_time":   float(chunk.start_time),
        "end_time":     float(chunk.end_time),
        "timestamp":    format_timestamp(chunk.start_time),
        "token_count":  int(chunk.token_count),
        "segment_ids":  seg_ids,
        "source_type":  "audio_transcript",
        "speaker":      "professor",
    }


def build_metadata_list(chunks: List[Any]) -> List[Dict[str, Any]]:
    """
    Build a metadata list for a batch of chunks.

    Parameters
    ----------
    chunks : list[Chunk]

    Returns
    -------
    list[dict]
        One metadata dict per chunk, in the same order.
    """
    return [build_chunk_metadata(c) for c in chunks]


# ──────────────────────────────────────────────────────────────
# Search result formatter
# ──────────────────────────────────────────────────────────────
def build_search_result(
    text: str,
    metadata: Dict[str, Any],
    distance: float,
    chunk_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Format a ChromaDB query result into the canonical retrieval schema.

    Parameters
    ----------
    text : str
        The chunk text returned by ChromaDB.
    metadata : dict
        The metadata dict stored alongside the embedding.
    distance : float
        Cosine or L2 distance from the query (lower = more similar for L2;
        higher = more similar for cosine similarity).
    chunk_id : str, optional
        ChromaDB document ID.

    Returns
    -------
    dict
        Example::

            {
                "text":       "KMP algorithm improves string matching",
                "lecture_id": "lecture_04",
                "timestamp":  "02:02",
                "start_time": 122.4,
                "end_time":   129.7,
                "score":      0.88,
                "chunk_id":   "lecture_04_chunk_005",
            }
    """
    # Convert distance to a 0–1 similarity score (works for cosine distance)
    score = round(1.0 - float(distance), 4)

    return {
        "text":       text,
        "lecture_id": metadata.get("lecture_id", "unknown"),
        "timestamp":  metadata.get("timestamp", format_timestamp(metadata.get("start_time", 0))),
        "start_time": metadata.get("start_time", 0.0),
        "end_time":   metadata.get("end_time", 0.0),
        "score":      score,
        "chunk_id":   chunk_id or "",
        "source_type": metadata.get("source_type", "audio_transcript"),
    }


# ──────────────────────────────────────────────────────────────
# Stats helper
# ──────────────────────────────────────────────────────────────
def summarise_metadata(metadatas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute aggregate statistics over a list of chunk metadata dicts.

    Parameters
    ----------
    metadatas : list[dict]

    Returns
    -------
    dict
        Keys: ``num_chunks``, ``lectures``, ``total_audio_seconds``.
    """
    if not metadatas:
        return {"num_chunks": 0, "lectures": [], "total_audio_seconds": 0.0}

    lectures = sorted({m.get("lecture_id", "") for m in metadatas})
    total_duration = sum(
        m.get("end_time", 0.0) - m.get("start_time", 0.0)
        for m in metadatas
    )
    return {
        "num_chunks":          len(metadatas),
        "lectures":            lectures,
        "num_lectures":        len(lectures),
        "total_audio_seconds": round(total_duration, 2),
    }
