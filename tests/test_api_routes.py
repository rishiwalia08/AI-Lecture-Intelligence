"""
tests/test_api_routes.py
--------------------------
API route tests using FastAPI TestClient with mocked rag_bridge.

No RAG models, Ollama server, or external services required.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure project root is on path
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))


# ──────────────────────────────────────────────────────────────
# Fixtures — mock RAGBridge
# ──────────────────────────────────────────────────────────────
def _make_mock_bridge(ready: bool = True, answer: str = "Test answer.") -> MagicMock:
    bridge = MagicMock()
    bridge.ready  = ready
    bridge.error  = None if ready else "Init failed"
    bridge.ask.return_value = {
        "answer":  answer,
        "sources": [
            {
                "lecture_id": "lecture_07",
                "timestamp":  "14:02",
                "start_time": 842.0,
                "end_time":   860.0,
                "chunk_id":   "lecture_07_chunk_042",
            }
        ],
    }
    return bridge


@pytest.fixture()
def client():
    """TestClient with RAGBridge and lifespan both mocked."""
    mock_bridge = _make_mock_bridge()
    with (
        patch("backend.services.rag_bridge.get_rag_bridge", return_value=mock_bridge),
        patch("backend.app.routes.get_rag_bridge", return_value=mock_bridge),
        patch("backend.app.main.get_rag_bridge", return_value=mock_bridge),
    ):
        from backend.app.main import app
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c, mock_bridge


@pytest.fixture()
def client_not_ready():
    """TestClient where RAGBridge reports not ready."""
    mock_bridge = _make_mock_bridge(ready=False)
    with (
        patch("backend.services.rag_bridge.get_rag_bridge", return_value=mock_bridge),
        patch("backend.app.routes.get_rag_bridge", return_value=mock_bridge),
        patch("backend.app.main.get_rag_bridge", return_value=mock_bridge),
    ):
        from backend.app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c, mock_bridge


# ──────────────────────────────────────────────────────────────
# GET /health
# ──────────────────────────────────────────────────────────────
class TestHealth:
    def test_returns_200(self, client) -> None:
        c, _ = client
        r = c.get("/health")
        assert r.status_code == 200

    def test_status_ok(self, client) -> None:
        c, _ = client
        r = c.get("/health")
        assert r.json()["status"] == "ok"

    def test_rag_ready_true(self, client) -> None:
        c, _ = client
        r = c.get("/health")
        assert r.json()["rag_ready"] is True

    def test_rag_ready_false_when_not_initialised(self, client_not_ready) -> None:
        c, _ = client_not_ready
        r = c.get("/health")
        assert r.json()["rag_ready"] is False

    def test_version_present(self, client) -> None:
        c, _ = client
        data = c.get("/health").json()
        assert "version" in data

    def test_message_present(self, client) -> None:
        c, _ = client
        data = c.get("/health").json()
        assert "message" in data


# ──────────────────────────────────────────────────────────────
# POST /ask
# ──────────────────────────────────────────────────────────────
class TestAsk:
    def test_returns_200(self, client) -> None:
        c, _ = client
        r = c.post("/ask", json={"query": "What is gradient descent?"})
        assert r.status_code == 200

    def test_answer_present(self, client) -> None:
        c, _ = client
        r = c.post("/ask", json={"query": "What is backpropagation?"})
        assert "answer" in r.json()

    def test_sources_present(self, client) -> None:
        c, _ = client
        r = c.post("/ask", json={"query": "What is backpropagation?"})
        assert "sources" in r.json()

    def test_source_has_required_fields(self, client) -> None:
        c, _ = client
        r = c.post("/ask", json={"query": "KMP algorithm"})
        src = r.json()["sources"][0]
        for key in ("lecture_id", "timestamp", "start_time", "end_time"):
            assert key in src

    def test_query_time_present(self, client) -> None:
        c, _ = client
        r = c.post("/ask", json={"query": "test"})
        assert "query_time_s" in r.json()

    def test_empty_query_returns_422(self, client) -> None:
        c, _ = client
        r = c.post("/ask", json={"query": ""})
        assert r.status_code == 422

    def test_blank_query_returns_422(self, client) -> None:
        c, _ = client
        r = c.post("/ask", json={"query": "   "})
        assert r.status_code == 422

    def test_missing_query_returns_422(self, client) -> None:
        c, _ = client
        r = c.post("/ask", json={})
        assert r.status_code == 422

    def test_rag_not_ready_returns_503(self, client_not_ready) -> None:
        c, _ = client_not_ready
        r = c.post("/ask", json={"query": "test"})
        assert r.status_code == 503

    def test_lecture_filter_passed_to_bridge(self, client) -> None:
        c, bridge = client
        c.post("/ask", json={"query": "test", "lecture_filter": "lecture_03"})
        call_kwargs = bridge.ask.call_args
        assert call_kwargs.kwargs.get("lecture_filter") == "lecture_03"

    def test_top_k_passed_to_bridge(self, client) -> None:
        c, bridge = client
        c.post("/ask", json={"query": "test", "top_k": 8})
        assert bridge.ask.call_args.kwargs.get("top_n") == 8

    def test_rag_bridge_called_once(self, client) -> None:
        c, bridge = client
        c.post("/ask", json={"query": "What is attention?"})
        bridge.ask.assert_called_once()


# ──────────────────────────────────────────────────────────────
# POST /speech_query
# ──────────────────────────────────────────────────────────────
class TestSpeechQuery:
    @patch("backend.app.routes.transcribe_upload")
    def test_returns_200(self, mock_transcribe, client) -> None:
        mock_transcribe.return_value = "What is gradient descent?"
        c, _ = client
        r = c.post(
            "/speech_query",
            files={"audio": ("test.wav", io.BytesIO(b"fake-audio"), "audio/wav")},
        )
        assert r.status_code == 200

    @patch("backend.app.routes.transcribe_upload")
    def test_transcribed_query_present(self, mock_transcribe, client) -> None:
        mock_transcribe.return_value = "What is backpropagation?"
        c, _ = client
        r = c.post(
            "/speech_query",
            files={"audio": ("q.wav", io.BytesIO(b"fake"), "audio/wav")},
        )
        data = r.json()
        assert "transcribed_query" in data
        assert data["transcribed_query"] == "What is backpropagation?"

    @patch("backend.app.routes.transcribe_upload")
    def test_answer_present(self, mock_transcribe, client) -> None:
        mock_transcribe.return_value = "KMP algorithm"
        c, _ = client
        r = c.post(
            "/speech_query",
            files={"audio": ("a.wav", io.BytesIO(b"fake"), "audio/wav")},
        )
        assert "answer" in r.json()

    @patch("backend.app.routes.transcribe_upload", side_effect=RuntimeError("Whisper failed"))
    def test_transcription_failure_returns_422(self, mock_transcribe, client) -> None:
        c, _ = client
        r = c.post(
            "/speech_query",
            files={"audio": ("bad.wav", io.BytesIO(b"corrupt"), "audio/wav")},
        )
        assert r.status_code == 422

    def test_no_file_returns_422(self, client) -> None:
        c, _ = client
        r = c.post("/speech_query")
        assert r.status_code == 422


# ──────────────────────────────────────────────────────────────
# Root redirect
# ──────────────────────────────────────────────────────────────
class TestRoot:
    def test_root_returns_200(self, client) -> None:
        c, _ = client
        r = c.get("/")
        assert r.status_code == 200

    def test_root_has_message(self, client) -> None:
        c, _ = client
        r = c.get("/")
        assert "message" in r.json()
