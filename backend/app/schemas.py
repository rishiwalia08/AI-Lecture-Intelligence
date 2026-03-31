"""
backend/app/schemas.py
------------------------
Pydantic request/response models for the Interactive Lecture Intelligence API.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ──────────────────────────────────────────────────────────────
# Requests
# ──────────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    """Body for POST /ask."""
    query: str = Field(..., min_length=1, max_length=1000,
                       description="The student's question about a lecture topic.")
    lecture_filter: Optional[str] = Field(
        None, description="Restrict retrieval to a specific lecture_id, e.g. 'lecture_07'."
    )
    top_k: int = Field(5, ge=1, le=20,
                       description="Number of results to retrieve and return.")
    provider: Optional[str] = Field(
        None, description="Override LLM provider: 'ollama' or 'groq'."
    )

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be blank.")
        return v.strip()


# ──────────────────────────────────────────────────────────────
# Shared sub-models
# ──────────────────────────────────────────────────────────────
class SourceItem(BaseModel):
    """A single lecture source cited in an answer."""
    lecture_id:  str   = Field(..., description="Lecture identifier.")
    timestamp:   str   = Field(..., description="Human-readable start time, e.g. '14:02'.")
    start_time:  float = Field(0.0, description="Start time in seconds.")
    end_time:    float = Field(0.0, description="End time in seconds.")
    chunk_id:    str   = Field("",  description="Internal chunk ID.")
    video_url:   Optional[str] = Field(None, description="Playable video URL at source timestamp when available.")


# ──────────────────────────────────────────────────────────────
# Responses
# ──────────────────────────────────────────────────────────────
class AnswerResponse(BaseModel):
    """Response from POST /ask."""
    answer:       str                = Field(..., description="LLM-generated answer.")
    sources:      List[SourceItem]   = Field(default_factory=list)
    query_time_s: float              = Field(0.0, description="Total wall-clock time.")
    grounded:     bool               = Field(True, description="Whether the answer is grounded.")

    model_config = {"json_schema_extra": {
        "example": {
            "answer": "Backpropagation updates weights using gradient descent.",
            "sources": [{"lecture_id": "lecture_07", "timestamp": "14:02",
                         "start_time": 842.0, "end_time": 860.0, "chunk_id": ""}],
            "query_time_s": 1.24,
            "grounded": True,
        }
    }}


class SpeechQueryResponse(AnswerResponse):
    """Response from POST /speech_query — adds the transcribed query text."""
    transcribed_query: str = Field("", description="Query text as transcribed from audio.")

    model_config = {"json_schema_extra": {
        "example": {
            "transcribed_query": "What is gradient descent?",
            "answer":    "Gradient descent minimises the loss function iteratively.",
            "sources":   [],
            "query_time_s": 3.5,
            "grounded": True,
        }
    }}


class HealthResponse(BaseModel):
    """Response from GET /health."""
    status:    str  = "ok"
    version:   str  = "1.0.0"
    rag_ready: bool = False
    documents_indexed: int = 0
    message:   str  = ""


class IngestYoutubeRequest(BaseModel):
    """Body for POST /ingest_youtube."""
    url: str = Field(..., min_length=8, max_length=2000, description="YouTube video URL")
    lecture_id: Optional[str] = Field(None, description="Optional custom lecture_id")


class IngestResponse(BaseModel):
    """Response after ingesting a video/audio source."""
    lecture_id: str
    num_segments: int
    num_chunks: int
    indexed_vectors: int
    duration_s: float
    message: str


class LectureSummaryItem(BaseModel):
    lecture_id: str
    key_topics: List[str] = Field(default_factory=list)
    summary: str


class SummariesResponse(BaseModel):
    lectures: List[LectureSummaryItem] = Field(default_factory=list)


class TranscriptSegment(BaseModel):
    """A single transcript segment with timing."""
    text: str = Field(..., description="Segment text content")
    start: float = Field(default=0.0, description="Start time in seconds")
    duration: float = Field(default=0.0, description="Duration in seconds")


class IngestYoutubeTranscriptRequest(BaseModel):
    """Body for POST /ingest_youtube_transcript (client-side fetched)."""
    video_id: str = Field(..., description="YouTube video ID")
    transcript: List[TranscriptSegment] = Field(..., description="Pre-fetched transcript segments")
    title: Optional[str] = Field(None, description="Optional lecture title")
    lecture_id: Optional[str] = Field(None, description="Optional custom lecture_id")


class IngestTextRequest(BaseModel):
    """Body for POST /ingest_text (manual transcript)."""
    text: str = Field(..., min_length=10, max_length=1_000_000, description="Raw text transcript/notes")
    title: Optional[str] = Field(None, description="Optional lecture title")
    lecture_id: Optional[str] = Field(None, description="Optional custom lecture_id")
