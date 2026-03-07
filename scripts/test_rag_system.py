"""
scripts/test_rag_system.py
---------------------------
Phase 5 end-to-end RAG test and demonstration script.

Usage
-----
    # Basic text query (Ollama, default)
    python scripts/test_rag_system.py --query "What is gradient descent?"

    # Use Groq API (set GROQ_API_KEY env var first)
    python scripts/test_rag_system.py --query "What is KMP?" --provider groq --model llama3-8b-8192

    # Audio query (Whisper transcribes first)
    python scripts/test_rag_system.py --audio path/to/question.wav

    # Skip reranker (faster)
    python scripts/test_rag_system.py --query "attention mechanism" --no-rerank

    # Run RAGAS evaluation from file
    python scripts/test_rag_system.py --eval data/eval_samples.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.llm.llm_loader import LLMConfig
from src.llm.rag_prompt import PromptConfig
from src.services.rag_service import RAGService, RAGServiceConfig
from src.services.retrieval_service import ServiceConfig
from src.evaluation.rag_evaluator import RAGEvaluator, RAGSample
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Speech RAG — Phase 5: LLM Answer Generation Test"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--query",  "-q", type=str, help="Text query string.")
    mode.add_argument("--audio",  "-a", type=str, help="Path to audio query file.")
    mode.add_argument("--eval",   "-e", type=str, help="Path to JSON evaluation dataset.")

    parser.add_argument("--config",   default="config/config.yaml")
    parser.add_argument("--provider", default=None,
                        choices=["ollama", "groq"],
                        help="Override LLM provider from config.")
    parser.add_argument("--model",    default=None, help="Override LLM model from config.")
    parser.add_argument("--lecture",  default=None, metavar="ID",
                        help="Filter retrieval to a specific lecture_id.")
    parser.add_argument("--top-k",   type=int, default=5,
                        help="Number of results to retrieve.")
    parser.add_argument("--no-rerank", action="store_true",
                        help="Disable the BGE cross-encoder reranker.")
    parser.add_argument("--rebuild-bm25", action="store_true",
                        help="Rebuild BM25 index before querying.")
    return parser.parse_args()


# ──────────────────────────────────────────────────────────────
# Pretty printer
# ──────────────────────────────────────────────────────────────
def _print_result(result: dict, query: str) -> None:
    print(f"\n{'═' * 72}")
    print(f"  QUERY  : {query}")
    print(f"{'═' * 72}")

    answer = result.get("answer", "")
    print(f"\n  ANSWER :\n")
    # Indent answer lines
    for line in answer.split("\n"):
        print(f"    {line}")

    sources = result.get("sources", [])
    if sources:
        print(f"\n  SOURCES ({len(sources)}):")
        for i, s in enumerate(sources, 1):
            print(
                f"    [{i}] {s['lecture_id']:15s}"
                f"  @ {s.get('timestamp', '??:??'):8s}"
                f"  ({s.get('start_time', 0):.0f}s – {s.get('end_time', 0):.0f}s)"
            )
    print(f"\n{'═' * 72}\n")


# ──────────────────────────────────────────────────────────────
# Build service
# ──────────────────────────────────────────────────────────────
def _build_service(args: argparse.Namespace, config_path: Path) -> RAGService:
    svc_cfg = RAGServiceConfig.from_yaml(config_path, project_root=_PROJECT_ROOT)

    # CLI overrides
    if args.provider:
        svc_cfg.llm_cfg.provider = args.provider
    if args.model:
        svc_cfg.llm_cfg.model = args.model
    if args.no_rerank:
        svc_cfg.retrieval_cfg.reranker_cfg.enabled = False

    return RAGService(svc_cfg)


# ──────────────────────────────────────────────────────────────
# Evaluation mode
# ──────────────────────────────────────────────────────────────
def _run_evaluation(eval_path: str, svc: RAGService) -> None:
    path = Path(eval_path)
    if not path.exists():
        print(f"[ERROR] Evaluation file not found: {path}")
        sys.exit(1)

    with path.open(encoding="utf-8") as fh:
        items = json.load(fh)

    print(f"\nRunning RAGAS evaluation on {len(items)} sample(s)…\n")
    samples = []
    for item in items:
        query    = item["query"]
        result   = svc.ask_question(query)
        contexts = [s.get("text", "") for s in result.get("sources", [])]
        samples.append(RAGSample(
            query=query,
            answer=result["answer"],
            contexts=contexts,
            ground_truth=item.get("ground_truth", ""),
        ))

    evaluator = RAGEvaluator()
    report    = evaluator.evaluate(samples)
    print(RAGEvaluator.format_report(report))


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────
def main() -> None:
    args        = _parse_args()
    config_path = _PROJECT_ROOT / args.config

    if not config_path.exists():
        print(f"[ERROR] Config not found: {config_path}")
        sys.exit(1)

    svc = _build_service(args, config_path)

    # BM25 index
    if args.rebuild_bm25 or svc._retrieval._searcher.bm25.size == 0:
        svc._retrieval.build_bm25_index()

    # Evaluation mode
    if args.eval:
        _run_evaluation(args.eval, svc)
        return

    # Determine query source
    if args.audio:
        audio_path = Path(args.audio)
        if not audio_path.exists():
            print(f"[ERROR] Audio file not found: {audio_path}")
            sys.exit(1)
        raw_query  = str(audio_path)
        input_type = "audio"
    elif args.query:
        raw_query  = args.query
        input_type = "text"
    else:
        print("[ERROR] Provide --query, --audio, or --eval.")
        sys.exit(1)

    result = svc.ask_question(
        query=raw_query,
        input_type=input_type,
        top_n=args.top_k,
        lecture_filter=args.lecture,
    )

    display_q = raw_query if input_type == "text" else f"[audio] {raw_query}"
    _print_result(result, display_q)


if __name__ == "__main__":
    main()
