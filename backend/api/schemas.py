from __future__ import annotations

from pydantic import BaseModel, Field


class QARequest(BaseModel):
    question: str = Field(..., min_length=3)


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2)


class Reference(BaseModel):
    chunk_id: str
    text: str
    start_time: float
    end_time: float
    timestamp: str
    youtube_link: str | None = None


class SummarySection(BaseModel):
    topic: str
    start_time: float
    end_time: float


class SummaryResponse(BaseModel):
    tldr: str
    detailed_notes: str
    key_points: list[str]
    topic_breakdown: list[SummarySection]


class Flashcard(BaseModel):
    front: str
    back: str


class FlashcardsResponse(BaseModel):
    video_id: str
    flashcards: list[Flashcard]


class ChatResponse(BaseModel):
    answer: str
    answer_type: str = Field(default="grounded")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    references: list[Reference]


class QAResponse(BaseModel):
    answer: str
    answer_type: str = Field(default="grounded")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    references: list[Reference]


class TopicSearchResponse(BaseModel):
    query: str
    explanation: str
    results: list[Reference]


class GraphNode(BaseModel):
    id: str | int
    label: str | None = None
    group: str | None = None
    name: str | None = None
    val: int | None = None


class GraphLink(BaseModel):
    source: str | int
    target: str | int
    label: str | None = None


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    links: list[GraphLink]
