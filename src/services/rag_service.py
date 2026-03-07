"""
src/services/rag_service.py
-----------------------------
Unified RAG pipeline for the Interactive Lecture Intelligence system — Phase 5.

Composes Phase 4 retrieval with Phase 5 LLM generation:

    user query (text | audio)
        │
        ▼ RetrievalService.retrieve_context()
        │
        ▼ AnswerGenerator.generate()
        │
        ▼ GeneratedAnswer  +  rag_metrics.csv row

Usage
-----
    from src.services.rag_service import RAGService, RAGServiceConfig

    svc    = RAGService.from_config("config/config.yaml")
    result = svc.ask_question("What is gradient descent?")
    print(result["answer"])
    for src in result["sources"]:
        print(src["lecture_id"], src["timestamp"])
"""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.llm.answer_generator import AnswerGenerator, GeneratedAnswer
from src.llm.llm_loader import LLMConfig, load_llm
from src.llm.rag_prompt import NO_MATERIAL_FOUND, PromptConfig
from src.services.retrieval_service import RetrievalService, ServiceConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
@dataclass
class RAGServiceConfig:
    """
    Top-level configuration for :class:`RAGService`.

    Attributes
    ----------
    retrieval_cfg : ServiceConfig
    llm_cfg : LLMConfig
    prompt_cfg : PromptConfig
    rag_metrics_path : Path
    """
    retrieval_cfg:    ServiceConfig  = field(default_factory=ServiceConfig)
    llm_cfg:          LLMConfig      = field(default_factory=LLMConfig)
    prompt_cfg:       PromptConfig   = field(default_factory=PromptConfig)
    rag_metrics_path: Path           = Path("logs/rag_metrics.csv")

    @classmethod
    def from_yaml(cls, config_path: str | Path, project_root: Path | None = None) -> "RAGServiceConfig":
        root = project_root or Path.cwd()
        with open(config_path) as fh:
            raw = yaml.safe_load(fh)

        retrieval_cfg = ServiceConfig.from_yaml(config_path, project_root=root)
        llm_cfg       = LLMConfig.from_dict(raw)
        return cls(
            retrieval_cfg=retrieval_cfg,
            llm_cfg=llm_cfg,
            rag_metrics_path=root / raw.get("rag_metrics_path", "logs/rag_metrics.csv"),
        )


# ──────────────────────────────────────────────────────────────
# Metrics
# ──────────────────────────────────────────────────────────────
_RAG_COLS = [
    "timestamp_utc", "query", "retrieval_time_s", "llm_time_s",
    "total_time_s", "input_tokens", "output_tokens",
    "num_sources", "grounded", "is_refusal",
]


def _init_rag_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=_RAG_COLS).writeheader()


def _append_rag_metrics(path: Path, row: Dict[str, Any]) -> None:
    with path.open("a", newline="", encoding="utf-8") as fh:
        csv.DictWriter(fh, fieldnames=_RAG_COLS).writerow(row)


# ──────────────────────────────────────────────────────────────
# RAGService
# ──────────────────────────────────────────────────────────────
class RAGService:
    """
    Unified RAG pipeline — retrieval + LLM generation.

    Parameters
    ----------
    config : RAGServiceConfig, optional
    """

    def __init__(self, config: Optional[RAGServiceConfig] = None) -> None:
        self.config = config or RAGServiceConfig()

        # Phase 4 retrieval
        self._retrieval = RetrievalService(self.config.retrieval_cfg)

        # Phase 5 LLM
        llm             = load_llm(self.config.llm_cfg)
        self._generator = AnswerGenerator(llm, self.config.prompt_cfg)

        _init_rag_csv(self.config.rag_metrics_path)
        logger.info(
            "RAGService ready — provider=%s, model=%s.",
            self.config.llm_cfg.provider,
            self.config.llm_cfg.model,
        )

    @classmethod
    def from_config(cls, config_path: str | Path) -> "RAGService":
        """Load everything from a YAML config file."""
        cfg = RAGServiceConfig.from_yaml(config_path)
        return cls(cfg)

    # ──────────────────────────────────────────────────────────
    # Main pipeline
    # ──────────────────────────────────────────────────────────
    def ask_question(
        self,
        query:          str,
        input_type:     str = "text",
        top_n:          Optional[int] = None,
        lecture_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        End-to-end RAG pipeline: retrieve → generate → validate → log.

        Parameters
        ----------
        query : str
            Raw question text **or** path to an audio file when
            ``input_type="audio"``.
        input_type : str
            ``"text"`` (default) or ``"audio"``.
        top_n : int, optional
            Override the number of retrieved chunks to pass to the LLM.
        lecture_filter : str, optional
            Restrict retrieval to a specific ``lecture_id``.

        Returns
        -------
        dict
            ``{"answer": str, "sources": list[dict]}``
            Each source has ``lecture_id``, ``timestamp``, ``start_time``,
            ``end_time``, ``chunk_id``.
        """
        t_total = time.perf_counter()
        logger.info("RAGService.ask_question(): '%s'", query[:120])

        # ── Step 1: Retrieval ─────────────────────────────────
        t_ret = time.perf_counter()
        try:
            chunks = self._retrieval.retrieve_context(
                user_query=query,
                input_type=input_type,
                top_n=top_n,
                lecture_filter=lecture_filter,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Retrieval failed: %s", exc)
            chunks = []
        retrieval_time = time.perf_counter() - t_ret

        # ── Empty retrieval guard ─────────────────────────────
        if not chunks:
            logger.warning("Retrieval returned no chunks — skipping LLM.")
            self._log_metrics(query, retrieval_time, 0.0, 0, 0, 0, False, True)
            return {"answer": NO_MATERIAL_FOUND, "sources": []}

        # ── Step 2: LLM generation ────────────────────────────
        t_llm = time.perf_counter()
        result: GeneratedAnswer = self._generator.generate(query, chunks)
        llm_time = time.perf_counter() - t_llm

        total_time = time.perf_counter() - t_total
        logger.info(
            "RAG complete: ret=%.2fs, llm=%.2fs, total=%.2fs.",
            retrieval_time, llm_time, total_time,
        )

        # ── Metrics ───────────────────────────────────────────
        self._log_metrics(
            query, retrieval_time, llm_time,
            result.token_usage.input_tokens,
            result.token_usage.output_tokens,
            len(result.sources),
            result.grounded,
            result.is_refusal,
        )

        return {
            "answer":  result.answer,
            "sources": [s.model_dump() for s in result.sources],
        }

    # ──────────────────────────────────────────────────────────
    # Internal
    # ──────────────────────────────────────────────────────────
    def _log_metrics(
        self,
        query: str,
        retrieval_time: float,
        llm_time: float,
        input_tokens: int,
        output_tokens: int,
        num_sources: int,
        grounded: bool,
        is_refusal: bool,
    ) -> None:
        _append_rag_metrics(self.config.rag_metrics_path, {
            "timestamp_utc":   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "query":           query[:200],
            "retrieval_time_s": round(retrieval_time, 4),
            "llm_time_s":      round(llm_time, 4),
            "total_time_s":    round(retrieval_time + llm_time, 4),
            "input_tokens":    input_tokens,
            "output_tokens":   output_tokens,
            "num_sources":     num_sources,
            "grounded":        grounded,
            "is_refusal":      is_refusal,
        })
