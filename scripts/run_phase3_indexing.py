"""
scripts/run_phase3_indexing.py
--------------------------------
Phase 3 entrypoint: embedding generation and vector indexing pipeline.

Reads Phase 2 transcript JSON files, chunks them, generates BGE-M3
embeddings, and indexes everything into a ChromaDB persistent collection.

Usage
-----
    python scripts/run_phase3_indexing.py [--config config/config.yaml]
                                          [--reset]
                                          [--limit N]
                                          [--dry-run]

Pipeline
--------
1. Glob all ``data/transcripts/*_transcript.json`` files.
2. For each transcript:
   a. Create token-aware overlapping chunks.
   b. Save chunks to ``data/chunks/``.
3. Load BGE-M3 embedder (once).
4. For each lecture: embed all chunks in batches.
5. Upsert embeddings + metadata into ChromaDB.
6. Print validation statistics.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import List

import yaml
from tqdm import tqdm

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.embedding.chunking import (
    Chunk,
    ChunkConfig,
    create_chunks,
    save_chunks,
)
from src.embedding.embedder import Embedder, EmbedderConfig
from src.retrieval.metadata_builder import build_metadata_list, summarise_metadata
from src.vectorstore.chroma_manager import ChromaConfig, ChromaManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Speech RAG — Phase 3: Embedding & Vector Indexing"
    )
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument(
        "--reset", action="store_true",
        help="Delete the existing collection and reindex from scratch.",
    )
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Process only the first N transcript files.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Chunk transcripts but skip embedding and indexing.",
    )
    return parser.parse_args()


# ──────────────────────────────────────────────────────────────
# Config helpers
# ──────────────────────────────────────────────────────────────
def _load_config(path: Path) -> dict:
    with path.open() as fh:
        return yaml.safe_load(fh)


def _build_chunk_config(cfg: dict) -> ChunkConfig:
    return ChunkConfig(
        chunk_size=cfg.get("chunk_size", 500),
        chunk_overlap=cfg.get("chunk_overlap", 50),
        min_chunk_tokens=cfg.get("min_chunk_tokens", 20),
    )


def _build_embedder_config(cfg: dict) -> EmbedderConfig:
    return EmbedderConfig(
        model_name=cfg.get("embedding_model", "BAAI/bge-m3"),
        batch_size=cfg.get("embedding_batch_size", 32),
    )


def _build_chroma_config(cfg: dict, project_root: Path) -> ChromaConfig:
    return ChromaConfig(
        db_path=str(project_root / cfg.get("vector_db_path", "vector_db")),
        collection_name=cfg.get("vector_collection", "lecture_index"),
    )


# ──────────────────────────────────────────────────────────────
# Transcript loader
# ──────────────────────────────────────────────────────────────
def _load_transcript(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


# ──────────────────────────────────────────────────────────────
# Pipeline steps
# ──────────────────────────────────────────────────────────────
def step1_chunk_transcripts(
    transcript_files: List[Path],
    chunk_cfg: ChunkConfig,
    chunks_dir: Path,
    dry_run: bool,
) -> List[Chunk]:
    """Chunk all transcripts and return the combined chunk list."""
    logger.info("═" * 60)
    logger.info("STEP 1 — Chunking transcripts (%d files)", len(transcript_files))
    logger.info("═" * 60)

    all_chunks: List[Chunk] = []
    for tf in tqdm(transcript_files, desc="Chunking", unit="lecture"):
        try:
            transcript = _load_transcript(tf)
            chunks = create_chunks(transcript, chunk_cfg)
            all_chunks.extend(chunks)
            if not dry_run:
                save_chunks(chunks, chunks_dir)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to chunk '%s': %s", tf.name, exc)

    logger.info("STEP 1 complete: %d total chunks from %d transcripts.",
                len(all_chunks), len(transcript_files))
    return all_chunks


def step2_embed_and_index(
    all_chunks: List[Chunk],
    embedder: Embedder,
    manager: ChromaManager,
    dry_run: bool,
) -> int:
    """Embed all chunks grouped by lecture and upsert into ChromaDB."""
    logger.info("═" * 60)
    logger.info("STEP 2 — Embedding & indexing %d chunks", len(all_chunks))
    logger.info("═" * 60)

    if dry_run:
        logger.info("[DRY-RUN] Skipping embedding and indexing.")
        return 0

    if not all_chunks:
        logger.warning("No chunks to index.")
        return 0

    # Group by lecture to keep tqdm informative
    lectures: dict[str, List[Chunk]] = {}
    for c in all_chunks:
        lectures.setdefault(c.lecture_id, []).append(c)

    total_indexed = 0
    for lecture_id, chunks in tqdm(lectures.items(), desc="Indexing", unit="lecture"):
        try:
            embeddings = embedder.embed_chunks(chunks)
            metadatas  = build_metadata_list(chunks)
            total_indexed += manager.upsert(chunks, embeddings, metadatas)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to index '%s': %s", lecture_id, exc)

    logger.info("STEP 2 complete: %d vectors indexed.", total_indexed)
    return total_indexed


# ──────────────────────────────────────────────────────────────
# Validation & summary
# ──────────────────────────────────────────────────────────────
def _validate_and_report(
    all_chunks: List[Chunk],
    manager: ChromaManager,
    elapsed: float,
    dry_run: bool,
) -> None:
    stats = summarise_metadata([
        {
            "lecture_id": c.lecture_id,
            "start_time": c.start_time,
            "end_time":   c.end_time,
        }
        for c in all_chunks
    ])
    vector_count = 0 if dry_run else manager.count()

    lines = [
        "",
        "╔══════════════════════════════════════════════════╗",
        "║       PHASE 3 INDEXING PIPELINE — SUMMARY        ║",
        "╠══════════════════════════════════════════════════╣",
        f"║  Transcripts processed : {len(stats.get('lectures', [])):< 24d}║",
        f"║  Total chunks          : {stats.get('num_chunks', 0):< 24d}║",
        f"║  Vectors in ChromaDB   : {vector_count:< 24d}║",
        f"║  Total audio covered   : {stats.get('total_audio_seconds', 0):<23.1f}s║",
        f"║  Elapsed time          : {elapsed:<23.1f}s║",
        "╚══════════════════════════════════════════════════╝",
        "",
    ]
    for line in lines:
        logger.info(line)


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────
def main() -> None:
    args          = _parse_args()
    project_root  = _PROJECT_ROOT
    config_path   = project_root / args.config

    if not config_path.exists():
        logger.error("Config not found: '%s'", config_path)
        sys.exit(1)

    cfg = _load_config(config_path)

    chunk_cfg    = _build_chunk_config(cfg)
    embedder_cfg = _build_embedder_config(cfg)
    chroma_cfg   = _build_chroma_config(cfg, project_root)

    transcripts_dir = project_root / cfg.get("transcripts_path", "data/transcripts")
    chunks_dir      = project_root / cfg.get("chunks_path", "data/chunks")
    chunks_dir.mkdir(parents=True, exist_ok=True)

    # Discover transcript files
    transcript_files = sorted(transcripts_dir.glob("*_transcript.json"))
    if not transcript_files:
        logger.warning(
            "No transcript files found in '%s'. Run Phase 2 first.", transcripts_dir
        )

    if args.limit:
        transcript_files = transcript_files[: args.limit]
        logger.info("--limit %d: processing %d transcripts.", args.limit, len(transcript_files))

    logger.info(
        "Phase 3 indexing pipeline started. transcripts=%d  dry_run=%s  reset=%s",
        len(transcript_files), args.dry_run, args.reset,
    )

    start_time = time.time()

    # ── Step 1: Chunk ──────────────────────────────────────────
    all_chunks = step1_chunk_transcripts(
        transcript_files, chunk_cfg, chunks_dir, dry_run=args.dry_run
    )

    # ── Set up embedder and vector store ──────────────────────
    embedder = Embedder(embedder_cfg)
    manager  = ChromaManager(chroma_cfg)

    if args.reset and not args.dry_run:
        logger.info("--reset: wiping existing collection.")
        manager.delete_collection()

    # ── Step 2: Embed & index ─────────────────────────────────
    step2_embed_and_index(all_chunks, embedder, manager, dry_run=args.dry_run)

    elapsed = time.time() - start_time
    _validate_and_report(all_chunks, manager, elapsed, dry_run=args.dry_run)
    logger.info("Phase 3 pipeline finished in %.1f seconds.", elapsed)


if __name__ == "__main__":
    main()
