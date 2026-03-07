"""
scripts/test_retrieval.py
--------------------------
Phase 4 retrieval testing and demonstration script.

Usage
-----
    # Text query
    python scripts/test_retrieval.py --query "What is gradient descent?"

    # Audio query (path to any Whisper-compatible audio file)
    python scripts/test_retrieval.py --audio path/to/query.wav

    # Filter to a specific lecture
    python scripts/test_retrieval.py --query "KMP algorithm" --lecture lecture_01

    # Disable reranker (faster, BM25+vector only)
    python scripts/test_retrieval.py --query "attention mechanism" --no-rerank

    # Return more results
    python scripts/test_retrieval.py --query "backpropagation" --top-k 10
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.services.retrieval_service import RetrievalService, ServiceConfig
from src.retrieval.reranker import RerankerConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Speech RAG — Phase 4: Retrieval Test Script"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--query", "-q",  type=str, help="Text query string.")
    group.add_argument("--audio", "-a",  type=str, help="Path to audio query file.")

    parser.add_argument("--config",   default="config/config.yaml", help="YAML config path.")
    parser.add_argument("--lecture",  default=None, metavar="ID",   help="Filter by lecture_id.")
    parser.add_argument("--top-k",    type=int, default=5,          help="Number of results.")
    parser.add_argument("--no-rerank", action="store_true",         help="Skip reranker.")
    parser.add_argument("--rebuild-bm25", action="store_true",
                        help="Rebuild the BM25 index before querying.")
    return parser.parse_args()


# ──────────────────────────────────────────────────────────────
# Pretty printer
# ──────────────────────────────────────────────────────────────
def _print_results(results: list, query: str) -> None:
    divider = "─" * 70
    print(f"\n{'═' * 70}")
    print(f"  QUERY : {query}")
    print(f"  RESULTS: {len(results)}")
    print(f"{'═' * 70}")

    if not results:
        print("  ⚠  No results returned. Make sure Phase 3 indexing has been run.")
        print(f"{'═' * 70}\n")
        return

    for i, r in enumerate(results, start=1):
        snippet = r["text"].replace("\n", " ")[:100]
        print(f"\n  [{i}] {r['lecture_id']}  @  {r['timestamp']}")
        print(f"       Score : {r['score']:.4f}")
        print(f"       Range : {r['start_time']:.1f}s → {r['end_time']:.1f}s")
        print(f"       Text  : {snippet}…" if len(r["text"]) > 100 else f"       Text  : {snippet}")
        print(f"       {divider}")

    print()


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────
def main() -> None:
    args = _parse_args()

    config_path = _PROJECT_ROOT / args.config
    if not config_path.exists():
        print(f"[ERROR] Config not found: {config_path}")
        sys.exit(1)

    # ── Build service ─────────────────────────────────────────
    svc_cfg = ServiceConfig.from_yaml(config_path, project_root=_PROJECT_ROOT)

    if args.no_rerank:
        svc_cfg.reranker_cfg.enabled = False

    svc = RetrievalService(svc_cfg)

    # ── BM25 index ────────────────────────────────────────────
    if args.rebuild_bm25 or svc._searcher.bm25.size == 0:
        svc.build_bm25_index()

    # ── Determine input type ──────────────────────────────────
    if args.audio:
        audio_path = Path(args.audio)
        if not audio_path.exists():
            print(f"[ERROR] Audio file not found: {audio_path}")
            sys.exit(1)
        raw_query  = str(audio_path)
        input_type = "audio"
    else:
        raw_query  = args.query
        input_type = "text"

    # ── Retrieve ──────────────────────────────────────────────
    results = svc.retrieve_context(
        user_query=raw_query,
        input_type=input_type,
        top_n=args.top_k,
        lecture_filter=args.lecture,
    )

    # ── Display ───────────────────────────────────────────────
    display_query = raw_query if input_type == "text" else f"[audio] {raw_query}"
    _print_results(results, display_query)

    logger.info("Retrieval complete — %d results for '%s'.", len(results), raw_query[:80])


if __name__ == "__main__":
    main()
