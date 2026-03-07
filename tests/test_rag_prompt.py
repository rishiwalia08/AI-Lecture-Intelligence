"""
tests/test_rag_prompt.py
--------------------------
Unit tests for src.llm.rag_prompt
"""

from __future__ import annotations

import pytest

from src.llm.rag_prompt import (
    CANNOT_FIND_PHRASE,
    NO_MATERIAL_FOUND,
    PromptBuilder,
    PromptConfig,
    _seconds_to_mmss,
)


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────
def _make_chunk(idx: int = 0, lecture: str = "lecture_01") -> dict:
    return {
        "chunk_id":   f"{lecture}_chunk_{idx:03d}",
        "text":       f"Chunk {idx}: The KMP algorithm uses a prefix table to avoid redundant comparisons.",
        "lecture_id": lecture,
        "start_time": float(idx * 60),
        "end_time":   float((idx + 1) * 60),
        "timestamp":  f"{idx:02d}:00",
    }


SAMPLE_CHUNKS = [_make_chunk(i) for i in range(3)]
QUERY = "What is the KMP algorithm?"


# ──────────────────────────────────────────────────────────────
# _seconds_to_mmss helper
# ──────────────────────────────────────────────────────────────
class TestSecondsToMmss:
    def test_whole_minutes(self) -> None:
        assert _seconds_to_mmss(120.0) == "02:00"

    def test_partial_minutes(self) -> None:
        assert _seconds_to_mmss(90.0) == "01:30"

    def test_zero(self) -> None:
        assert _seconds_to_mmss(0.0) == "00:00"

    def test_large_value(self) -> None:
        assert _seconds_to_mmss(3661.0) == "61:01"


# ──────────────────────────────────────────────────────────────
# PromptConfig
# ──────────────────────────────────────────────────────────────
class TestPromptConfig:
    def test_defaults(self) -> None:
        cfg = PromptConfig()
        assert cfg.max_context_chunks > 0
        assert cfg.max_chunk_chars > 0
        assert cfg.include_timestamps is True


# ──────────────────────────────────────────────────────────────
# PromptBuilder.build_context
# ──────────────────────────────────────────────────────────────
class TestBuildContext:
    def test_returns_str(self) -> None:
        b = PromptBuilder()
        ctx = b.build_context(SAMPLE_CHUNKS)
        assert isinstance(ctx, str)

    def test_empty_chunks_returns_empty(self) -> None:
        b = PromptBuilder()
        assert b.build_context([]) == ""

    def test_source_numbers_present(self) -> None:
        b = PromptBuilder()
        ctx = b.build_context(SAMPLE_CHUNKS)
        assert "[Source 1]" in ctx
        assert "[Source 2]" in ctx

    def test_lecture_id_in_context(self) -> None:
        b = PromptBuilder()
        ctx = b.build_context(SAMPLE_CHUNKS)
        assert "lecture_01" in ctx

    def test_timestamp_included(self) -> None:
        b = PromptBuilder(PromptConfig(include_timestamps=True))
        ctx = b.build_context(SAMPLE_CHUNKS)
        assert "@" in ctx

    def test_timestamp_excluded_when_disabled(self) -> None:
        b = PromptBuilder(PromptConfig(include_timestamps=False))
        ctx = b.build_context(SAMPLE_CHUNKS)
        assert "@" not in ctx

    def test_max_context_chunks_respected(self) -> None:
        cfg = PromptConfig(max_context_chunks=2)
        b   = PromptBuilder(cfg)
        ctx = b.build_context(SAMPLE_CHUNKS)  # 3 chunks, limit is 2
        assert "[Source 3]" not in ctx
        assert "[Source 2]" in ctx

    def test_chunk_text_truncated(self) -> None:
        long_chunk = {**_make_chunk(), "text": "word " * 300}
        cfg = PromptConfig(max_chunk_chars=50)
        b   = PromptBuilder(cfg)
        ctx = b.build_context([long_chunk])
        assert "…" in ctx


# ──────────────────────────────────────────────────────────────
# PromptBuilder.build_prompt
# ──────────────────────────────────────────────────────────────
class TestBuildPrompt:
    def test_contains_question_and_answer_header(self) -> None:
        b = PromptBuilder()
        p = b.build_prompt(QUERY, SAMPLE_CHUNKS)
        assert "Question:" in p
        assert "Answer:" in p

    def test_query_in_prompt(self) -> None:
        b = PromptBuilder()
        p = b.build_prompt(QUERY, SAMPLE_CHUNKS)
        assert QUERY in p

    def test_context_in_prompt(self) -> None:
        b = PromptBuilder()
        p = b.build_prompt(QUERY, SAMPLE_CHUNKS)
        assert "Context:" in p


# ──────────────────────────────────────────────────────────────
# PromptBuilder.build_messages
# ──────────────────────────────────────────────────────────────
class TestBuildMessages:
    def test_returns_two_messages(self) -> None:
        b = PromptBuilder()
        msgs = b.build_messages(QUERY, SAMPLE_CHUNKS)
        assert len(msgs) == 2

    def test_system_role_first(self) -> None:
        b = PromptBuilder()
        msgs = b.build_messages(QUERY, SAMPLE_CHUNKS)
        assert msgs[0]["role"] == "system"

    def test_user_role_second(self) -> None:
        b = PromptBuilder()
        msgs = b.build_messages(QUERY, SAMPLE_CHUNKS)
        assert msgs[1]["role"] == "user"

    def test_query_in_user_message(self) -> None:
        b = PromptBuilder()
        msgs = b.build_messages(QUERY, SAMPLE_CHUNKS)
        assert QUERY in msgs[1]["content"]


# ──────────────────────────────────────────────────────────────
# Hallucination guard methods
# ──────────────────────────────────────────────────────────────
class TestHallucinationGuard:
    def test_is_refusal_true(self) -> None:
        assert PromptBuilder.is_refusal(CANNOT_FIND_PHRASE) is True

    def test_is_refusal_case_insensitive(self) -> None:
        assert PromptBuilder.is_refusal(CANNOT_FIND_PHRASE.upper()) is True

    def test_is_refusal_false_for_normal_answer(self) -> None:
        assert PromptBuilder.is_refusal("KMP uses a prefix table.") is False

    def test_grounding_check_true_when_overlap(self) -> None:
        # chunk has 'algorithm' — answer also uses it
        chunk  = {"text": "KMP algorithm uses prefix table", "lecture_id": "x",
                  "start_time": 0, "end_time": 10}
        answer = "The KMP algorithm uses a prefix table."
        assert PromptBuilder.answer_references_context(answer, [chunk]) is True

    def test_grounding_check_false_when_no_overlap(self) -> None:
        chunk  = {"text": "calculus differential equations", "lecture_id": "x",
                  "start_time": 0, "end_time": 10}
        answer = "Backpropagation is completely different."
        # 'backpropagation' not in context, 'completely' not in context, 'different' not in context
        assert PromptBuilder.answer_references_context(answer, [chunk]) is False

    def test_grounding_check_empty_chunks_false(self) -> None:
        assert PromptBuilder.answer_references_context("anything", []) is False
