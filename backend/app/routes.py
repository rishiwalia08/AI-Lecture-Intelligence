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
    IngestYoutubeTranscriptRequest,
    IngestTextRequest,
    SummariesResponse,
    QueryRequest,
    SourceItem,
    SpeechQueryResponse,
)
from backend.services.ingestion_service import (
    attach_video_urls,
    get_summaries,
    ingest_local_media,
    ingest_youtube,
    ingest_transcript_segments,
    ingest_raw_text,
)
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
    
    # Get document count from vector store if RAG is ready
    documents_indexed = 0
    if rag_ready and bridge._svc is not None:
        try:
            documents_indexed = bridge._svc._vectorstore.count()
        except Exception as e:
            logger.warning("Could not retrieve document count: %s", e)
    
    return HealthResponse(
        status="ok",
        version="1.0.0",
        rag_ready=rag_ready,
        documents_indexed=documents_indexed,
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

    # Check if vector store has any indexed documents
    try:
        doc_count = bridge._svc._vectorstore.count() if bridge._svc else 0
        if doc_count == 0:
            logger.warning("/ask: vector store is empty")
            return AnswerResponse(
                answer="No lecture has been ingested yet. Please upload a video or audio file first, then ask your question.",
                sources=[],
                query_time_s=0.0,
                grounded=False,
            )
    except Exception as e:
        logger.warning("/ask: could not check document count: %s", e)

    try:
        result = bridge.ask(
            query=req.query,
            top_n=req.top_k,
            lecture_filter=req.lecture_filter,
            provider=req.provider,
        )
    except RuntimeError as e:
        # Handle model loading / initialization errors
        if "not ready" in str(e).lower():
            logger.error("/ask: RAG service not ready: %s", e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI model is temporarily unavailable. Please try again in a moment.",
            ) from e
        logger.error("/ask: runtime error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI model is temporarily unavailable. Please try again in a moment.",
        ) from e
    except MemoryError as e:
        logger.error("/ask: out of memory: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI model is temporarily unavailable. Please try again in a moment.",
        ) from e
    except Exception as exc:  # noqa: BLE001
        logger.error("/ask error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI model is temporarily unavailable. Please try again in a moment.",
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
    except RuntimeError as e:
        # Handle transcription timeouts and other runtime errors
        if "timed out" in str(e).lower():
            logger.error("Transcription timed out: %s", e)
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail=str(e),
            ) from e
        logger.error("Transcription runtime error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as exc:  # noqa: BLE001
        logger.error("Transcription failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Audio transcription failed: {exc}",
        ) from exc

    # Check if vector store has any indexed documents
    try:
        doc_count = bridge._svc._vectorstore.count() if bridge._svc else 0
        if doc_count == 0:
            logger.warning("/speech_query: vector store is empty")
            return SpeechQueryResponse(
                transcribed_query=transcribed_query,
                answer="No lecture has been ingested yet. Please upload a video or audio file first, then ask your question.",
                sources=[],
                query_time_s=0.0,
                grounded=False,
            )
    except Exception as e:
        logger.warning("/speech_query: could not check document count: %s", e)

    # ── RAG ───────────────────────────────────────────────────
    try:
        result = bridge.ask(
            query=transcribed_query,
            top_n=top_k,
            lecture_filter=lecture_filter,
        )
    except RuntimeError as e:
        # Handle model loading / initialization errors
        if "not ready" in str(e).lower():
            logger.error("/speech_query: RAG service not ready: %s", e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI model is temporarily unavailable. Please try again in a moment.",
            ) from e
        logger.error("/speech_query: runtime error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI model is temporarily unavailable. Please try again in a moment.",
        ) from e
    except MemoryError as e:
        logger.error("/speech_query: out of memory: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI model is temporarily unavailable. Please try again in a moment.",
        ) from e
    except Exception as exc:  # noqa: BLE001
        logger.error("/speech_query RAG error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI model is temporarily unavailable. Please try again in a moment.",
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
    """
    Upload and ingest a video/audio file.
    
    - Validates file size (max 50MB)
    - Transcribes with Whisper (timeout: 120s)
    - Cleans up temp file after processing
    """
    tmp_path = None
    try:
        data = await media.read()
        
        # File size validation (50MB max)
        max_size_bytes = 50 * 1024 * 1024  # 50MB
        if len(data) > max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large ({len(data) / (1024*1024):.1f}MB). Maximum size is 50MB. "
                       f"For larger files, consider trimming the audio first.",
            )
        
        suffix = Path(media.filename or "upload.mp4").suffix or ".mp4"
        tmp_path = Path("tmp") / f"upload_{int(time.time())}{suffix}"
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(data)
        
        logger.info("/ingest_video: file='%s', size=%dMB", tmp_path.name, len(data) / (1024*1024))

        payload = ingest_local_media(tmp_path, lecture_id=lecture_id)
        return IngestResponse(**payload)
    except HTTPException:
        # Re-raise HTTP exceptions (file size, etc)
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("/ingest_video error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video ingestion failed: {exc}",
        ) from exc
    finally:
        # Clean up temp file
        try:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
                logger.debug("Cleaned up temp file: %s", tmp_path)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to clean up temp file: %s", e)


@router.post(
    "/ingest_youtube_transcript",
    response_model=IngestResponse,
    tags=["ingestion"],
    summary="Ingest a pre-fetched YouTube transcript (client-side extraction).",
)
async def ingest_youtube_transcript_route(req: IngestYoutubeTranscriptRequest) -> IngestResponse:
    """
    Ingest a YouTube transcript that was already fetched client-side.

    This endpoint allows the frontend to bypass server-side YouTube blocking
    by extracting the transcript client-side and sending it to the backend.

    - Client fetches transcript using youtube-transcript npm package
    - Client POSTs the transcript data here
    - Backend chunks, embeds, and indexes into ChromaDB
    """
    try:
        # Convert request segments to dict format
        transcript_dicts = [seg.model_dump() for seg in req.transcript]
        payload = ingest_transcript_segments(
            transcript_segments=transcript_dicts,
            title=req.title,
            lecture_id=req.lecture_id,
            video_id=req.video_id,
            source_url=f"https://www.youtube.com/watch?v={req.video_id}",
        )
        return IngestResponse(**payload)
    except ValueError as e:
        logger.error("/ingest_youtube_transcript validation error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as exc:  # noqa: BLE001
        logger.error("/ingest_youtube_transcript error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcript ingestion failed: {exc}",
        ) from exc


@router.post(
    "/ingest_text",
    response_model=IngestResponse,
    tags=["ingestion"],
    summary="Ingest raw text as a lecture (manual transcript).",
)
async def ingest_text_route(req: IngestTextRequest) -> IngestResponse:
    """
    Ingest raw text directly into the vector store.

    Useful for:
    - Manually pasted lecture notes/transcripts
    - Student summaries
    - Raw text documents

    The text is chunked and embedded automatically.
    """
    try:
        payload = ingest_raw_text(
            text=req.text,
            title=req.title,
            lecture_id=req.lecture_id,
        )
        return IngestResponse(**payload)
    except ValueError as e:
        logger.error("/ingest_text validation error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as exc:  # noqa: BLE001
        logger.error("/ingest_text error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Text ingestion failed: {exc}",
        ) from exc


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

