"""
tests/test_reranker.py
------------------------
Unit tests for src.retrieval.reranker

All tests mock sentence_transformers.CrossEncoder — no GPU or download required.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.retrieval.reranker import Reranker, RerankerConfig


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────
def _make_candidates(n: int = 5) -> List[Dict[str, Any]]:
    return [
        {
            "chunk_id":   f"c{i:03d}",
            "text":       f"This is candidate chunk {i} about machine learning.",
            "lecture_id": "lecture_01",
            "start_time": float(i * 10),
            "end_time":   float((i + 1) * 10),
            "rrf_score":  float(1.0 / (i + 1)),
        }
        for i in range(n)
    ]


def _mock_cross_encoder(scores: List[float]) -> MagicMock:
    model = MagicMock()
    model.predict.return_value = np.array(scores, dtype=np.float32)
    return model


# ──────────────────────────────────────────────────────────────
# RerankerConfig
# ──────────────────────────────────────────────────────────────
class TestRerankerConfig:
    def test_defaults(self) -> None:
        cfg = RerankerConfig()
        assert cfg.top_n > 0
        assert cfg.batch_size > 0
        assert cfg.enabled is True

    def test_disabled_flag(self) -> None:
        cfg = RerankerConfig(enabled=False)
        assert cfg.enabled is False


# ──────────────────────────────────────────────────────────────
# Reranker class
# ──────────────────────────────────────────────────────────────
class TestRerankerInit:
    def test_model_not_loaded_on_init(self) -> None:
        r = Reranker()
        assert not r.is_loaded()


class TestRerank:
    @patch("sentence_transformers.CrossEncoder", autospec=False)
    def test_returns_list(self, mock_cls) -> None:
        mock_cls.return_value = _mock_cross_encoder([0.5, 0.3, 0.9, 0.1, 0.7])
        r = Reranker(RerankerConfig(top_n=3))
        result = r.rerank("gradient descent", _make_candidates(5))
        assert isinstance(result, list)

    @patch("sentence_transformers.CrossEncoder", autospec=False)
    def test_top_n_respected(self, mock_cls) -> None:
        mock_cls.return_value = _mock_cross_encoder([0.5, 0.3, 0.9, 0.1, 0.7])
        r = Reranker(RerankerConfig(top_n=3))
        result = r.rerank("gradient descent", _make_candidates(5))
        assert len(result) == 3

    @patch("sentence_transformers.CrossEncoder", autospec=False)
    def test_sorted_by_descending_score(self, mock_cls) -> None:
        scores = [0.5, 0.3, 0.9, 0.1, 0.7]
        mock_cls.return_value = _mock_cross_encoder(scores)
        r = Reranker(RerankerConfig(top_n=5))
        result = r.rerank("test", _make_candidates(5))
        result_scores = [item["rerank_score"] for item in result]
        assert result_scores == sorted(result_scores, reverse=True)

    @patch("sentence_transformers.CrossEncoder", autospec=False)
    def test_rerank_score_key_present(self, mock_cls) -> None:
        mock_cls.return_value = _mock_cross_encoder([0.8])
        r = Reranker(RerankerConfig(top_n=1))
        result = r.rerank("query", _make_candidates(1))
        assert "rerank_score" in result[0]

    @patch("sentence_transformers.CrossEncoder", autospec=False)
    def test_rerank_score_is_float(self, mock_cls) -> None:
        mock_cls.return_value = _mock_cross_encoder([0.6, 0.4, 0.9])
        r = Reranker(RerankerConfig(top_n=3))
        result = r.rerank("query", _make_candidates(3))
        for item in result:
            assert isinstance(item["rerank_score"], float)

    def test_empty_candidates_returns_empty(self) -> None:
        r = Reranker()
        result = r.rerank("gradient descent", [])
        assert result == []

    def test_disabled_reranker_skips_model(self) -> None:
        """With enabled=False, reranker should return first top_n without loading model."""
        r = Reranker(RerankerConfig(enabled=False, top_n=2))
        candidates = _make_candidates(5)
        result = r.rerank("query", candidates, top_n=2)
        assert len(result) == 2
        assert not r.is_loaded()   # model should NOT have been loaded

    def test_disabled_reranker_uses_rrf_score_as_fallback(self) -> None:
        r = Reranker(RerankerConfig(enabled=False, top_n=3))
        result = r.rerank("query", _make_candidates(5))
        for item in result:
            assert "rerank_score" in item

    @patch("sentence_transformers.CrossEncoder", autospec=False)
    def test_top_n_override(self, mock_cls) -> None:
        """top_n argument to rerank() should override config.top_n."""
        mock_cls.return_value = _mock_cross_encoder([0.9, 0.8, 0.7, 0.6, 0.5])
        r = Reranker(RerankerConfig(top_n=2))
        result = r.rerank("query", _make_candidates(5), top_n=4)
        assert len(result) == 4

    @patch("sentence_transformers.CrossEncoder", autospec=False)
    def test_model_loaded_lazily(self, mock_cls) -> None:
        mock_cls.return_value = _mock_cross_encoder([0.5])
        r = Reranker()
        assert not r.is_loaded()
        r.rerank("query", _make_candidates(1))
        assert r.is_loaded()
        assert mock_cls.call_count == 1
