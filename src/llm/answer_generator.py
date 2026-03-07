"""
src/llm/answer_generator.py
-----------------------------
Answer generation module for the Speech RAG pipeline — Phase 5.

Assembles retrieved chunks into a grounded prompt, invokes the LLM,
validates the response, and returns a structured :class:`GeneratedAnswer`
with sources and token usage.

Usage
-----
    from src.llm.answer_generator import AnswerGenerator
    from src.llm.llm_loader import LLMConfig, load_llm

    llm       = load_llm(LLMConfig(provider="ollama", model="llama3"))
    generator = AnswerGenerator(llm)
    result    = generator.generate(
        query  = "What is gradient descent?",
        chunks = retrieved_chunks,
    )
    print(result.answer)
    for src in result.sources:
        print(src.lecture_id, src.timestamp)
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.llm.llm_loader import LLMProvider, LLMResponse
from src.llm.rag_prompt import (
    CANNOT_FIND_PHRASE,
    NO_MATERIAL_FOUND,
    PromptBuilder,
    PromptConfig,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Output schema (Pydantic v2)
# ──────────────────────────────────────────────────────────────
class Source(BaseModel):
    """A single lecture source cited in the answer."""
    lecture_id:  str   = Field(..., description="Lecture identifier, e.g. 'lecture_07'.")
    timestamp:   str   = Field(..., description="Human-readable start time, e.g. '14:02'.")
    start_time:  float = Field(0.0, description="Start time in seconds.")
    end_time:    float = Field(0.0, description="End time in seconds.")
    chunk_id:    str   = Field("",  description="Internal chunk ID.")


class TokenUsage(BaseModel):
    """Token consumption for a single generation call."""
    input_tokens:  int   = 0
    output_tokens: int   = 0
    total_tokens:  int   = 0
    latency_s:     float = 0.0


class GeneratedAnswer(BaseModel):
    """
    The complete output of the RAG answer generation step.

    Attributes
    ----------
    answer : str
        The LLM-generated answer grounded in retrieved context.
    sources : list[Source]
        Lecture segments that were given to the LLM as context.
    token_usage : TokenUsage
        Token consumption and latency metrics.
    grounded : bool
        ``True`` if the answer appears to reference the context.
    is_refusal : bool
        ``True`` if the LLM returned the "cannot find" phrase.
    """
    answer:      str         = ""
    sources:     List[Source] = Field(default_factory=list)
    token_usage: TokenUsage   = Field(default_factory=TokenUsage)
    grounded:    bool         = True
    is_refusal:  bool         = False


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def _extract_sources(chunks: List[Dict[str, Any]]) -> List[Source]:
    """Convert retrieval result dicts to :class:`Source` objects."""
    sources = []
    for c in chunks:
        start = float(c.get("start_time", 0.0))
        end   = float(c.get("end_time",   0.0))
        ts    = c.get("timestamp") or f"{int(start) // 60:02d}:{int(start) % 60:02d}"
        sources.append(Source(
            lecture_id=c.get("lecture_id", "unknown"),
            timestamp=ts,
            start_time=start,
            end_time=end,
            chunk_id=c.get("chunk_id", ""),
        ))
    return sources


# ──────────────────────────────────────────────────────────────
# AnswerGenerator
# ──────────────────────────────────────────────────────────────
class AnswerGenerator:
    """
    Generates grounded answers from retrieved lecture chunks using an LLM.

    Parameters
    ----------
    llm : LLMProvider
        A loaded :class:`~src.llm.llm_loader.LLMProvider`.
    prompt_config : PromptConfig, optional
        Controls context formatting. Defaults to ``PromptConfig()``.
    """

    def __init__(
        self,
        llm: LLMProvider,
        prompt_config: Optional[PromptConfig] = None,
    ) -> None:
        self.llm     = llm
        self.builder = PromptBuilder(prompt_config)

    # ──────────────────────────────────────────────────────────
    # Core method
    # ──────────────────────────────────────────────────────────
    def generate(
        self,
        query:  str,
        chunks: List[Dict[str, Any]],
    ) -> GeneratedAnswer:
        """
        Generate a grounded answer for ``query`` using ``chunks`` as context.

        Parameters
        ----------
        query : str
            The user's question (cleaned or raw — both accepted).
        chunks : list[dict]
            Retrieved context chunks from
            :meth:`~src.services.retrieval_service.RetrievalService.retrieve_context`.
            Each dict must have ``"text"``, ``"lecture_id"``, ``"start_time"``,
            ``"end_time"`` keys.

        Returns
        -------
        GeneratedAnswer
            Structured answer with sources and token statistics.
        """
        logger.info("AnswerGenerator.generate(): query='%s', chunks=%d.", query[:80], len(chunks))

        # ── Empty-context guard ───────────────────────────────
        if not chunks:
            logger.warning("No chunks provided — returning no-material message.")
            return GeneratedAnswer(
                answer=NO_MATERIAL_FOUND,
                sources=[],
                grounded=False,
                is_refusal=True,
            )

        # ── Build prompt and call LLM ─────────────────────────
        messages = self.builder.build_messages(query, chunks)

        try:
            llm_response: LLMResponse = self.llm.generate(messages)
        except Exception as exc:  # noqa: BLE001
            logger.error("LLM generation failed: %s", exc)
            return GeneratedAnswer(
                answer=f"LLM error: {exc}",
                sources=_extract_sources(chunks),
                grounded=False,
            )

        answer = llm_response.content.strip()
        if not answer:
            answer = CANNOT_FIND_PHRASE

        # ── Hallucination checks ──────────────────────────────
        is_refusal = self.builder.is_refusal(answer)
        grounded   = (
            is_refusal  # refusal is a valid grounded response
            or self.builder.answer_references_context(answer, chunks)
        )

        if not grounded:
            logger.warning(
                "Answer may not be grounded in context: '%s…'", answer[:80]
            )

        # ── Build output ──────────────────────────────────────
        sources = _extract_sources(chunks)
        usage   = TokenUsage(
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
            total_tokens=llm_response.total_tokens,
            latency_s=llm_response.latency_s,
        )

        result = GeneratedAnswer(
            answer=answer,
            sources=sources,
            token_usage=usage,
            grounded=grounded,
            is_refusal=is_refusal,
        )
        logger.info(
            "Answer generated: %d chars, %d sources, grounded=%s, tokens=%d.",
            len(answer), len(sources), grounded, usage.total_tokens,
        )
        return result

    # ──────────────────────────────────────────────────────────
    # Convenience function
    # ──────────────────────────────────────────────────────────
    def generate_answer(
        self,
        query:  str,
        retrieved_chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Module-level compatible wrapper that returns a plain dict.

        Returns
        -------
        dict  Keys: ``"answer"``, ``"sources"``.
        """
        result = self.generate(query, retrieved_chunks)
        return {
            "answer":  result.answer,
            "sources": [s.model_dump() for s in result.sources],
        }
