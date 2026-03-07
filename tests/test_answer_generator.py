"""
tests/test_answer_generator.py
--------------------------------
Unit tests for src.llm.answer_generator

All LLM calls are mocked — no Ollama server or Groq key required.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from src.llm.answer_generator import AnswerGenerator, GeneratedAnswer, Source, TokenUsage
from src.llm.llm_loader import LLMResponse
from src.llm.rag_prompt import CANNOT_FIND_PHRASE, NO_MATERIAL_FOUND


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────
def _make_chunk(idx: int = 0) -> Dict[str, Any]:
    return {
        "chunk_id":   f"lecture_01_chunk_{idx:03d}",
        "text":       "Backpropagation is a method to update neural network weights using gradients.",
        "lecture_id": "lecture_07",
        "start_time": float(idx * 60 + 842),
        "end_time":   float(idx * 60 + 860),
        "timestamp":  "14:02",
    }


def _mock_llm(content: str = "Backpropagation uses gradients.", tokens: int = 20) -> MagicMock:
    llm = MagicMock()
    llm.generate.return_value = LLMResponse(
        content=content,
        model="test-model",
        input_tokens=tokens,
        output_tokens=tokens // 2,
        latency_s=0.5,
    )
    return llm


# ──────────────────────────────────────────────────────────────
# GeneratedAnswer model
# ──────────────────────────────────────────────────────────────
class TestGeneratedAnswer:
    def test_default_answer_is_empty(self) -> None:
        ga = GeneratedAnswer()
        assert ga.answer == ""

    def test_sources_default_empty(self) -> None:
        ga = GeneratedAnswer()
        assert ga.sources == []

    def test_grounded_default_true(self) -> None:
        ga = GeneratedAnswer()
        assert ga.grounded is True


# ──────────────────────────────────────────────────────────────
# AnswerGenerator.generate — normal case
# ──────────────────────────────────────────────────────────────
class TestGenerateNormal:
    def test_returns_generated_answer(self) -> None:
        gen = AnswerGenerator(_mock_llm())
        result = gen.generate("What is backpropagation?", [_make_chunk()])
        assert isinstance(result, GeneratedAnswer)

    def test_answer_is_str(self) -> None:
        gen = AnswerGenerator(_mock_llm("Backprop updates weights."))
        result = gen.generate("query", [_make_chunk()])
        assert isinstance(result.answer, str)
        assert len(result.answer) > 0

    def test_sources_extracted(self) -> None:
        gen = AnswerGenerator(_mock_llm())
        result = gen.generate("query", [_make_chunk(0), _make_chunk(1)])
        assert len(result.sources) == 2

    def test_source_lecture_id(self) -> None:
        gen = AnswerGenerator(_mock_llm())
        result = gen.generate("query", [_make_chunk()])
        assert result.sources[0].lecture_id == "lecture_07"

    def test_source_timestamp(self) -> None:
        gen = AnswerGenerator(_mock_llm())
        result = gen.generate("query", [_make_chunk()])
        assert result.sources[0].timestamp == "14:02"

    def test_token_usage_populated(self) -> None:
        gen = AnswerGenerator(_mock_llm(tokens=30))
        result = gen.generate("query", [_make_chunk()])
        assert result.token_usage.input_tokens == 30
        assert result.token_usage.output_tokens == 15

    def test_llm_called_once(self) -> None:
        llm = _mock_llm()
        gen = AnswerGenerator(llm)
        gen.generate("query", [_make_chunk()])
        llm.generate.assert_called_once()

    def test_grounded_true_for_relevant_answer(self) -> None:
        # Answer references 'backpropagation' which is in the chunk text
        gen = AnswerGenerator(_mock_llm("Backpropagation uses gradients."))
        result = gen.generate("query", [_make_chunk()])
        assert result.grounded is True


# ──────────────────────────────────────────────────────────────
# AnswerGenerator.generate — empty chunks guard
# ──────────────────────────────────────────────────────────────
class TestGenerateEmptyChunks:
    def test_empty_chunks_returns_no_material(self) -> None:
        llm = _mock_llm()
        gen = AnswerGenerator(llm)
        result = gen.generate("query", [])
        assert result.answer == NO_MATERIAL_FOUND

    def test_empty_chunks_llm_not_called(self) -> None:
        llm = _mock_llm()
        gen = AnswerGenerator(llm)
        gen.generate("query", [])
        llm.generate.assert_not_called()

    def test_empty_chunks_grounded_false(self) -> None:
        gen = AnswerGenerator(_mock_llm())
        result = gen.generate("query", [])
        assert result.grounded is False

    def test_empty_chunks_is_refusal_true(self) -> None:
        gen = AnswerGenerator(_mock_llm())
        result = gen.generate("query", [])
        assert result.is_refusal is True


# ──────────────────────────────────────────────────────────────
# AnswerGenerator.generate — LLM returns refusal phrase
# ──────────────────────────────────────────────────────────────
class TestGenerateRefusal:
    def test_refusal_detected(self) -> None:
        llm = _mock_llm(CANNOT_FIND_PHRASE)
        gen = AnswerGenerator(llm)
        result = gen.generate("query", [_make_chunk()])
        assert result.is_refusal is True

    def test_refusal_answer_still_grounded(self) -> None:
        """A refusal is a valid grounded response (not hallucination)."""
        llm = _mock_llm(CANNOT_FIND_PHRASE)
        gen = AnswerGenerator(llm)
        result = gen.generate("query", [_make_chunk()])
        assert result.grounded is True


# ──────────────────────────────────────────────────────────────
# AnswerGenerator.generate — LLM error handling
# ──────────────────────────────────────────────────────────────
class TestGenerateLLMError:
    def test_llm_exception_handled(self) -> None:
        llm = MagicMock()
        llm.generate.side_effect = RuntimeError("Connection refused")
        gen    = AnswerGenerator(llm)
        result = gen.generate("query", [_make_chunk()])
        assert "LLM error" in result.answer
        assert result.grounded is False

    def test_sources_still_populated_on_error(self) -> None:
        llm = MagicMock()
        llm.generate.side_effect = RuntimeError("Timeout")
        gen    = AnswerGenerator(llm)
        result = gen.generate("query", [_make_chunk()])
        assert len(result.sources) == 1


# ──────────────────────────────────────────────────────────────
# generate_answer() wrapper
# ──────────────────────────────────────────────────────────────
class TestGenerateAnswerWrapper:
    def test_returns_dict(self) -> None:
        gen    = AnswerGenerator(_mock_llm())
        result = gen.generate_answer("query", [_make_chunk()])
        assert isinstance(result, dict)
        assert "answer" in result
        assert "sources" in result

    def test_sources_is_list(self) -> None:
        gen    = AnswerGenerator(_mock_llm())
        result = gen.generate_answer("query", [_make_chunk()])
        assert isinstance(result["sources"], list)
