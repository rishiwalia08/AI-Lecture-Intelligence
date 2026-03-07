"""
src/evaluation/rag_evaluator.py
---------------------------------
RAGAS-based evaluation wrapper for the Speech RAG pipeline — Phase 5.

Evaluates the quality of generated answers against ground-truth references
using three RAGAS metrics:

  - **Faithfulness**: Does the answer factually align with the retrieved context?
  - **Context Precision**: Are the retrieved chunks actually relevant to the query?
  - **Answer Relevancy**: Does the answer address the user's question?

The evaluator degrades gracefully if ``ragas`` is not installed — it logs a
warning and returns empty metrics rather than crashing.

Usage
-----
    from src.evaluation.rag_evaluator import RAGEvaluator, RAGSample

    evaluator = RAGEvaluator()
    samples   = [
        RAGSample(
            query        = "What is backpropagation?",
            answer       = "Backpropagation updates weights using gradients.",
            contexts     = ["...retrieved chunk text..."],
            ground_truth = "Backpropagation is an algorithm ...",
        )
    ]
    report = evaluator.evaluate(samples)
    print(report)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────────────────────
class RAGSample(BaseModel):
    """
    A single evaluation sample for RAGAS.

    Attributes
    ----------
    query : str             The user's original question.
    answer : str            The RAG-generated answer.
    contexts : list[str]    The retrieved chunk texts provided to the LLM.
    ground_truth : str      The reference (gold) answer for this query.
    """
    query:        str
    answer:       str
    contexts:     List[str] = Field(default_factory=list)
    ground_truth: str       = ""


# ──────────────────────────────────────────────────────────────
# Evaluator
# ──────────────────────────────────────────────────────────────
class RAGEvaluator:
    """
    Evaluates RAG system output using RAGAS metrics.

    Parameters
    ----------
    llm : any, optional
        Language model used by RAGAS internally. If ``None``, RAGAS will
        attempt to use its default (typically requires an OpenAI key unless
        you configure a local model).
    embeddings : any, optional
        Embedding model used by RAGAS. Defaults to RAGAS built-in.
    """

    def __init__(self, llm=None, embeddings=None) -> None:
        self._llm        = llm
        self._embeddings = embeddings
        self._ragas_available = self._check_ragas()

    @staticmethod
    def _check_ragas() -> bool:
        try:
            import ragas  # type: ignore[import]  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "ragas is not installed — evaluation will return empty metrics. "
                "Install with: pip install ragas"
            )
            return False

    # ──────────────────────────────────────────────────────────
    # Main evaluation
    # ──────────────────────────────────────────────────────────
    def evaluate(self, samples: List[RAGSample]) -> Dict[str, Any]:
        """
        Evaluate a list of RAG samples and return metric scores.

        Parameters
        ----------
        samples : list[RAGSample]

        Returns
        -------
        dict
            ``{"faithfulness": float, "context_precision": float,
               "answer_relevancy": float, "num_samples": int}``
            All scores are in ``[0, 1]``.  Returns zeros if RAGAS is
            not installed or if evaluation fails.
        """
        if not samples:
            return self._empty_report(0)

        if not self._ragas_available:
            return self._empty_report(len(samples))

        try:
            return self._run_ragas(samples)
        except Exception as exc:  # noqa: BLE001
            logger.error("RAGAS evaluation failed: %s", exc)
            return self._empty_report(len(samples))

    def _run_ragas(self, samples: List[RAGSample]) -> Dict[str, Any]:
        from datasets import Dataset                                        # type: ignore[import]
        from ragas import evaluate                                          # type: ignore[import]
        from ragas.metrics import (                                         # type: ignore[import]
            answer_relevancy,
            context_precision,
            faithfulness,
        )

        data = {
            "question":    [s.query        for s in samples],
            "answer":      [s.answer       for s in samples],
            "contexts":    [s.contexts     for s in samples],
            "ground_truth":[s.ground_truth for s in samples],
        }
        dataset = Dataset.from_dict(data)

        kwargs: Dict[str, Any] = {}
        if self._llm:
            kwargs["llm"] = self._llm
        if self._embeddings:
            kwargs["embeddings"] = self._embeddings

        result = evaluate(
            dataset,
            metrics=[faithfulness, context_precision, answer_relevancy],
            **kwargs,
        )
        report = {
            "faithfulness":       round(float(result["faithfulness"]), 4),
            "context_precision":  round(float(result["context_precision"]), 4),
            "answer_relevancy":   round(float(result["answer_relevancy"]), 4),
            "num_samples":        len(samples),
        }
        logger.info("RAGAS evaluation: %s", report)
        return report

    @staticmethod
    def _empty_report(n: int) -> Dict[str, Any]:
        return {
            "faithfulness":      0.0,
            "context_precision": 0.0,
            "answer_relevancy":  0.0,
            "num_samples":       n,
        }

    # ──────────────────────────────────────────────────────────
    # File-based evaluation
    # ──────────────────────────────────────────────────────────
    def evaluate_from_file(self, path: str | Path) -> Dict[str, Any]:
        """
        Load evaluation samples from a JSON file and evaluate.

        Expected JSON format
        --------------------
        A list of objects:
        .. code-block:: json

            [
              {
                "query":        "What is backpropagation?",
                "answer":       "Backpropagation updates weights …",
                "contexts":     ["Retrieved chunk text …"],
                "ground_truth": "Backpropagation is an algorithm …"
              }
            ]

        Parameters
        ----------
        path : str | Path

        Returns
        -------
        dict
            RAGAS metric report.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Evaluation file not found: {path}")

        with path.open(encoding="utf-8") as fh:
            raw = json.load(fh)

        samples = [RAGSample(**item) for item in raw]
        logger.info("Loaded %d evaluation samples from '%s'.", len(samples), path)
        return self.evaluate(samples)

    # ──────────────────────────────────────────────────────────
    # Formatting
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def format_report(report: Dict[str, Any]) -> str:
        """Pretty-print a RAGAS report dict."""
        lines = [
            "",
            "╔═══════════════════════════════════════╗",
            "║       RAGAS EVALUATION REPORT          ║",
            "╠═══════════════════════════════════════╣",
            f"║  Faithfulness       : {report.get('faithfulness', 0):.4f}          ║",
            f"║  Context Precision  : {report.get('context_precision', 0):.4f}          ║",
            f"║  Answer Relevancy   : {report.get('answer_relevancy', 0):.4f}          ║",
            f"║  Samples evaluated  : {report.get('num_samples', 0):<18d}║",
            "╚═══════════════════════════════════════╝",
            "",
        ]
        return "\n".join(lines)
