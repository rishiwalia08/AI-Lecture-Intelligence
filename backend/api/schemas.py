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


class QAResponse(BaseModel):
    answer: str
    references: list[Reference]


class TopicSearchResponse(BaseModel):
    query: str
    explanation: str
    results: list[Reference]
