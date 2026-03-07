"""
tests/test_query_processor.py
--------------------------------
Unit tests for src.retrieval.query_processor
"""

from __future__ import annotations

import pytest

from src.retrieval.query_processor import (
    QueryProcessor,
    QueryProcessorConfig,
    process_query,
)


# ──────────────────────────────────────────────────────────────
# QueryProcessorConfig
# ──────────────────────────────────────────────────────────────
class TestQueryProcessorConfig:
    def test_defaults(self) -> None:
        cfg = QueryProcessorConfig()
        assert cfg.remove_stopwords is True
        assert cfg.lowercase is True
        assert cfg.min_token_length >= 1

    def test_extra_stopwords_default_empty(self) -> None:
        cfg = QueryProcessorConfig()
        assert cfg.extra_stopwords == []


# ──────────────────────────────────────────────────────────────
# QueryProcessor.process()
# ──────────────────────────────────────────────────────────────
class TestQueryProcessorProcess:
    def test_lowercases_input(self) -> None:
        qp = QueryProcessor()
        assert qp.process("KMP ALGORITHM") == "kmp algorithm"

    def test_removes_punctuation(self) -> None:
        qp = QueryProcessor(QueryProcessorConfig(remove_stopwords=False))
        result = qp.process("Hello, world!")
        assert "," not in result
        assert "!" not in result

    def test_strips_url(self) -> None:
        qp = QueryProcessor(QueryProcessorConfig(remove_stopwords=False))
        result = qp.process("See https://example.com for details")
        assert "https" not in result
        assert "example" not in result     # URL stripped

    def test_removes_stopwords(self) -> None:
        qp = QueryProcessor()
        result = qp.process("What is the KMP algorithm used for?")
        assert "what" not in result
        assert "is" not in result
        assert "the" not in result

    def test_min_token_length_applied(self) -> None:
        qp = QueryProcessor(QueryProcessorConfig(
            remove_stopwords=False, min_token_length=3
        ))
        result = qp.process("a ab abc abcd")
        tokens = result.split()
        assert all(len(t) >= 3 for t in tokens)

    def test_empty_string_returns_empty(self) -> None:
        qp = QueryProcessor()
        assert qp.process("") == ""
        assert qp.process("   ") == ""

    def test_only_stopwords_returns_empty(self) -> None:
        qp = QueryProcessor()
        assert qp.process("what is the") == ""

    def test_collapses_whitespace(self) -> None:
        qp = QueryProcessor(QueryProcessorConfig(remove_stopwords=False))
        result = qp.process("KMP    algorithm   works")
        assert "  " not in result

    def test_unicode_normalisation(self) -> None:
        qp = QueryProcessor(QueryProcessorConfig(remove_stopwords=False))
        result = qp.process("caf\u00e9 algorithm")   # 'é' as single codepoint
        assert "caf" in result

    def test_hyphens_preserved_inside_word(self) -> None:
        """Intra-word hyphens like 'bi-gram' should be kept."""
        qp = QueryProcessor(QueryProcessorConfig(remove_stopwords=False))
        result = qp.process("bi-gram model")
        assert "bi-gram" in result

    def test_no_stopword_removal_when_disabled(self) -> None:
        qp = QueryProcessor(QueryProcessorConfig(remove_stopwords=False))
        result = qp.process("what is the algorithm")
        assert "what" in result
        assert "is" in result
        assert "the" in result

    def test_extra_stopwords_respected(self) -> None:
        cfg = QueryProcessorConfig(extra_stopwords=["algorithm", "method"])
        qp  = QueryProcessor(cfg)
        result = qp.process("the kmp algorithm is a method")
        assert "algorithm" not in result
        assert "method" not in result


# ──────────────────────────────────────────────────────────────
# QueryProcessor.tokenize()
# ──────────────────────────────────────────────────────────────
class TestTokenize:
    def test_returns_list(self) -> None:
        qp = QueryProcessor()
        tokens = qp.tokenize("kmp algorithm")
        assert isinstance(tokens, list)

    def test_consistent_with_process_split(self) -> None:
        qp = QueryProcessor()
        text = "What is the KMP algorithm used for?"
        assert qp.tokenize(text) == qp.process(text).split()

    def test_empty_input_returns_empty_list(self) -> None:
        qp = QueryProcessor()
        assert qp.tokenize("") == []


# ──────────────────────────────────────────────────────────────
# Module-level convenience function
# ──────────────────────────────────────────────────────────────
class TestProcessQuery:
    def test_returns_str(self) -> None:
        assert isinstance(process_query("Hello world"), str)

    def test_uses_default_config(self) -> None:
        result = process_query("What exactly is the KMP algorithm?")
        assert "kmp" in result
        assert "what" not in result
