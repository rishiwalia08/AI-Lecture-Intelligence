"""
backend/app/routes.py
-----------------------
FastAPI route definitions for the Interactive Lecture Intelligence API.

Endpoints
---------
GET  /health            API liveness + RAG readiness check.
POST /ask               Text query → RAG → answer + sources.
POST /speech_query      Audio upload → Whisper → RAG → answer + sources.
GET  /knowledge_graph   Get knowledge graph data.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from backend.app.schemas import (
    AnswerResponse,
    HealthResponse,
    IngestResponse,
    IngestYoutubeRequest,
    SummariesResponse,
    QueryRequest,
    SourceItem,
    SpeechQueryResponse,
)
from backend.services.ingestion_service import attach_video_urls, get_summaries, ingest_local_media, ingest_youtube
from backend.services.rag_bridge import get_rag_bridge
from backend.services.speech_bridge import transcribe_upload
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Accepted audio MIME types / extensions
_AUDIO_TYPES = {
    "audio/wav", "audio/wave", "audio/x-wav",
    "audio/mpeg", "audio/mp3",
    "audio/ogg", "audio/webm",
    "audio/mp4", "audio/m4a",
    "application/octet-stream",   # some clients send this for audio
}


def _ensure_bridge_ready(bridge) -> None:
    if not bridge.ready and bridge.error is None:
        bridge.initialise()


# ──────────────────────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────────────────────
@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"],
    summary="API liveness and RAG readiness check.",
)
async def health(request: Request) -> HealthResponse:
    bridge   = get_rag_bridge()
    rag_ready = bridge.ready
    msg = "RAG pipeline ready." if rag_ready else f"RAG not ready: {bridge.error or 'initialising'}"
    return HealthResponse(
        status="ok",
        version="1.0.0",
        rag_ready=rag_ready,
        message=msg,
    )


# ──────────────────────────────────────────────────────────────
# Text ask
# ──────────────────────────────────────────────────────────────
@router.post(
    "/ask",
    response_model=AnswerResponse,
    tags=["retrieval"],
    summary="Answer a lecture question from text.",
)
async def ask(req: QueryRequest) -> AnswerResponse:
    """
    Run the full RAG pipeline for a text query.

    - Cleans and embeds the query.
    - Performs hybrid search (semantic + BM25, merged via RRF).
    - Reranks candidates with BGE cross-encoder.
    - Generates a grounded answer with the configured LLM.
    """
    bridge = get_rag_bridge()
    _ensure_bridge_ready(bridge)
    
    # Lazy initialization on first request
    if not bridge.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"RAG pipeline not ready. {bridge.error or 'Initializing, please retry.'}",
        )

    logger.info("/ask: query='%s'", req.query[:100])
    t0 = time.perf_counter()

    try:
        result = bridge.ask(
            query=req.query,
            top_n=req.top_k,
            lecture_filter=req.lecture_filter,
            provider=req.provider,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("/ask error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG pipeline error: {exc}",
        ) from exc

    elapsed = round(time.perf_counter() - t0, 3)
    sources_with_urls = attach_video_urls(result.get("sources", []))
    sources = [SourceItem(**s) for s in sources_with_urls]
    return AnswerResponse(
        answer=result.get("answer", ""),
        sources=sources,
        query_time_s=elapsed,
        grounded=True,
    )


# ──────────────────────────────────────────────────────────────
# Speech query
# ──────────────────────────────────────────────────────────────
@router.post(
    "/speech_query",
    response_model=SpeechQueryResponse,
    tags=["retrieval"],
    summary="Answer a lecture question from recorded audio.",
)
async def speech_query(
    audio:          UploadFile = File(..., description="Audio file (WAV, MP3, OGG, WebM, M4A)."),
    top_k:          int        = Form(5),
    lecture_filter: Optional[str] = Form(None),
) -> SpeechQueryResponse:
    """
    Pipeline: audio upload → Whisper transcription → RAG → answer.

    Accepts any Whisper-compatible audio format.  The transcription is
    returned alongside the answer so the frontend can display it.
    """
    bridge = get_rag_bridge()
    _ensure_bridge_ready(bridge)
    if not bridge.ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG pipeline not ready.",
        )

    # Validate content type loosely
    ct = (audio.content_type or "").lower()
    if ct and ct not in _AUDIO_TYPES:
        logger.warning("/speech_query: unexpected content_type '%s'.", ct)

    logger.info("/speech_query: file='%s', size≈unknown.", audio.filename)
    t0 = time.perf_counter()

    # ── Transcription ─────────────────────────────────────────
    try:
        audio_data        = await audio.read()
        transcribed_query = await transcribe_upload(audio_data, filename=audio.filename or "audio.wav")
    except Exception as exc:  # noqa: BLE001
        logger.error("Transcription failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Audio transcription failed: {exc}",
        ) from exc

    # ── RAG ───────────────────────────────────────────────────
    try:
        result = bridge.ask(
            query=transcribed_query,
            top_n=top_k,
            lecture_filter=lecture_filter,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("/speech_query RAG error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG pipeline error: {exc}",
        ) from exc

    elapsed = round(time.perf_counter() - t0, 3)
    sources_with_urls = attach_video_urls(result.get("sources", []))
    sources = [SourceItem(**s) for s in sources_with_urls]
    return SpeechQueryResponse(
        transcribed_query=transcribed_query,
        answer=result.get("answer", ""),
        sources=sources,
        query_time_s=elapsed,
        grounded=True,
    )


@router.post(
    "/ingest_youtube",
    response_model=IngestResponse,
    tags=["ingestion"],
    summary="Ingest a YouTube lecture URL into transcripts + vector index.",
)
async def ingest_youtube_route(req: IngestYoutubeRequest) -> IngestResponse:
    try:
        payload = ingest_youtube(req.url, lecture_id=req.lecture_id)
        return IngestResponse(**payload)
    except Exception as exc:  # noqa: BLE001
        logger.error("/ingest_youtube error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"YouTube ingestion failed: {exc}",
        ) from exc


@router.post(
    "/ingest_video",
    response_model=IngestResponse,
    tags=["ingestion"],
    summary="Upload a local video/audio file and ingest it.",
)
async def ingest_video_route(
    media: UploadFile = File(..., description="Video/audio file such as mp4, mp3, wav, m4a"),
    lecture_id: Optional[str] = Form(None),
) -> IngestResponse:
    try:
        data = await media.read()
        suffix = Path(media.filename or "upload.mp4").suffix or ".mp4"
        tmp_path = Path("tmp") / f"upload_{int(time.time())}{suffix}"
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(data)

        payload = ingest_local_media(tmp_path, lecture_id=lecture_id)
        return IngestResponse(**payload)
    except Exception as exc:  # noqa: BLE001
        logger.error("/ingest_video error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video ingestion failed: {exc}",
        ) from exc
    finally:
        try:
            if 'tmp_path' in locals() and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


@router.get(
    "/summaries",
    response_model=SummariesResponse,
    tags=["content"],
    summary="Return lecture summaries generated from transcript content.",
)
async def summaries_route() -> SummariesResponse:
    try:
        return SummariesResponse(**get_summaries())
    except Exception as exc:  # noqa: BLE001
        logger.error("/summaries error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load summaries: {exc}",
        ) from exc


# ──────────────────────────────────────────────────────────────
# Knowledge Graph
# ──────────────────────────────────────────────────────────────
@router.get("/knowledge_graph")
async def get_knowledge_graph(request: Request):
    """
    GET /knowledge_graph
    
    Returns the knowledge graph data if available.
    
    Returns:
        JSON with nodes and edges, or error message.
    """
    import json
    from pathlib import Path
    
    # Try to load graph JSON file
    graph_path = Path("data/knowledge_graph/concept_graph.json")
    
    if not graph_path.exists():
        logger.warning("/knowledge_graph: Graph file not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge graph not generated. Run: python scripts/build_concept_graph.py",
        )
    
    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)
        
        logger.info("/knowledge_graph: Returned graph with %d nodes", len(graph_data.get("nodes", [])))
        return graph_data
        
    except Exception as exc:
        logger.error("/knowledge_graph: Error loading graph: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading knowledge graph: {exc}",
        ) from exc

