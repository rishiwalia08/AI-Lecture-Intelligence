"""
tests/test_embedder.py
------------------------
Unit tests for src.embedding.embedder

All tests use a mocked SentenceTransformer — no model download or GPU needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from pathlib import Path

import numpy as np
import pytest

from src.embedding.embedder import Embedder, EmbedderConfig
from src.embedding.chunking import Chunk


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
DIM = 1024  # BGE-M3 output dimension


def _make_chunk(idx: int = 0, text: str = "Hello world.") -> Chunk:
    return Chunk(
        chunk_id    = f"lecture_01_chunk_{idx:03d}",
        text        = text,
        start_time  = float(idx * 10),
        end_time    = float((idx + 1) * 10),
        lecture_id  = "lecture_01",
        segment_ids = [f"{idx:03d}"],
        chunk_index = idx,
        token_count = len(text.split()),
    )


def _mock_st_model(dim: int = DIM) -> MagicMock:
    """Return a mock SentenceTransformer that returns random numpy arrays."""
    model = MagicMock()

    def encode_side_effect(texts, **kwargs):
        if isinstance(texts, str):
            return np.random.rand(dim).astype(np.float32)
        return np.random.rand(len(texts), dim).astype(np.float32)

    model.encode.side_effect = encode_side_effect
    model.get_sentence_embedding_dimension.return_value = dim
    return model


# ──────────────────────────────────────────────────────────────
# EmbedderConfig tests
# ──────────────────────────────────────────────────────────────
class TestEmbedderConfig:
    def test_defaults(self) -> None:
        cfg = EmbedderConfig()
        assert cfg.model_name == "BAAI/bge-m3"
        assert cfg.batch_size > 0
        assert cfg.normalize_embeddings is True

    def test_custom_values(self) -> None:
        cfg = EmbedderConfig(model_name="all-MiniLM-L6-v2", batch_size=16, device="cpu")
        assert cfg.batch_size == 16
        assert cfg.device == "cpu"


# ──────────────────────────────────────────────────────────────
# Embedder — generate_embedding
# ──────────────────────────────────────────────────────────────
class TestGenerateEmbedding:
    @patch("sentence_transformers.SentenceTransformer", autospec=False)
    def test_returns_list_of_floats(self, mock_cls) -> None:
        mock_cls.return_value = _mock_st_model()
        embedder = Embedder()
        vec = embedder.generate_embedding("KMP algorithm")
        assert isinstance(vec, list)
        assert all(isinstance(v, float) for v in vec)

    @patch("sentence_transformers.SentenceTransformer", autospec=False)
    def test_vector_has_correct_dim(self, mock_cls) -> None:
        mock_cls.return_value = _mock_st_model(DIM)
        embedder = Embedder()
        vec = embedder.generate_embedding("test")
        assert len(vec) == DIM

    @patch("sentence_transformers.SentenceTransformer", autospec=False)
    def test_model_loaded_lazily(self, mock_cls) -> None:
        """Model should only be loaded on first call, not on __init__."""
        embedder = Embedder()
        assert mock_cls.call_count == 0  # not yet loaded
        mock_cls.return_value = _mock_st_model()
        embedder.generate_embedding("hello")
        assert mock_cls.call_count == 1


# ──────────────────────────────────────────────────────────────
# Embedder — embed_chunks
# ──────────────────────────────────────────────────────────────
class TestEmbedChunks:
    @patch("sentence_transformers.SentenceTransformer", autospec=False)
    def test_empty_input_returns_empty(self, mock_cls) -> None:
        mock_cls.return_value = _mock_st_model()
        embedder = Embedder()
        result = embedder.embed_chunks([])
        assert result == []

    @patch("sentence_transformers.SentenceTransformer", autospec=False)
    def test_one_vector_per_chunk(self, mock_cls) -> None:
        mock_cls.return_value = _mock_st_model()
        embedder = Embedder()
        chunks = [_make_chunk(i) for i in range(5)]
        vecs = embedder.embed_chunks(chunks)
        assert len(vecs) == 5

    @patch("sentence_transformers.SentenceTransformer", autospec=False)
    def test_each_vector_is_list_of_floats(self, mock_cls) -> None:
        mock_cls.return_value = _mock_st_model()
        embedder = Embedder()
        chunks = [_make_chunk(0, "Hello."), _make_chunk(1, "World.")]
        vecs = embedder.embed_chunks(chunks)
        for v in vecs:
            assert isinstance(v, list)
            assert isinstance(v[0], float)

    @patch("sentence_transformers.SentenceTransformer", autospec=False)
    def test_embedding_dim_correct(self, mock_cls) -> None:
        mock_cls.return_value = _mock_st_model(DIM)
        embedder = Embedder()
        chunks = [_make_chunk(0)]
        vecs = embedder.embed_chunks(chunks)
        assert len(vecs[0]) == DIM


# ──────────────────────────────────────────────────────────────
# Embedder — embed_query
# ──────────────────────────────────────────────────────────────
class TestEmbedQuery:
    @patch("sentence_transformers.SentenceTransformer", autospec=False)
    def test_returns_list(self, mock_cls) -> None:
        mock_cls.return_value = _mock_st_model()
        embedder = Embedder()
        vec = embedder.embed_query("What is the KMP algorithm?")
        assert isinstance(vec, list)

    @patch("sentence_transformers.SentenceTransformer", autospec=False)
    def test_query_dim_matches_doc_dim(self, mock_cls) -> None:
        mock_cls.return_value = _mock_st_model(DIM)
        embedder = Embedder()
        q_vec = embedder.embed_query("Hello?")
        d_vec = embedder.generate_embedding("Hello!")
        assert len(q_vec) == len(d_vec)


# ──────────────────────────────────────────────────────────────
# Embedder — embedding_dim property
# ──────────────────────────────────────────────────────────────
class TestEmbeddingDimProperty:
    def test_dim_none_before_load(self) -> None:
        embedder = Embedder()
        assert embedder.embedding_dim is None

    @patch("sentence_transformers.SentenceTransformer", autospec=False)
    def test_dim_after_load(self, mock_cls) -> None:
        mock_cls.return_value = _mock_st_model(DIM)
        embedder = Embedder()
        embedder.generate_embedding("trigger load")
        assert embedder.embedding_dim == DIM
