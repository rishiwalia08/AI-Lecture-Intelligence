from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.schemas import (
    FlashcardsResponse,
    GraphResponse,
    QARequest,
    QAResponse,
    SearchRequest,
    SummaryResponse,
    TopicSearchResponse,
)
from db.repository import ArtifactRepository, MetadataRepository
from services.transcription import YoutubeTranscriptUnavailableError

router = APIRouter()

logger = logging.getLogger(__name__)

metadata_repo = MetadataRepository()
artifact_repo = ArtifactRepository()

pipeline = None
rag_service = None


def get_pipeline():
    global pipeline
    if pipeline is None:
        try:
            from services.pipeline import LecturePipeline

            pipeline = LecturePipeline()
        except Exception as exc:
            logger.exception("Failed to initialize lecture pipeline")
            raise HTTPException(
                status_code=503,
                detail=f"Pipeline initialization failed: {exc}",
            ) from exc
    return pipeline


def get_rag_service():
    global rag_service
    if rag_service is None:
        p = get_pipeline()
        from services.rag import RAGService

        rag_service = RAGService(p.llm_service, p.vector_store)
    return rag_service


@router.get("/videos")
def list_videos() -> dict:
    return {"videos": metadata_repo.list_videos()}


@router.get("/videos/{video_id}")
def get_video(video_id: str) -> dict:
    video = metadata_repo.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.post("/videos/ingest")
async def ingest_video(
    youtube_url: str | None = Form(default=None),
    title: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> dict:
    if not youtube_url and not file:
        raise HTTPException(status_code=400, detail="Provide either youtube_url or file")

    try:
        p = get_pipeline()

        if youtube_url:
            payload = p.ingest_from_youtube(youtube_url=youtube_url, title=title)
            return {"message": "Video ingested successfully", "video": payload}

        suffix = Path(file.filename or "lecture.mp4").suffix or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)

        payload = p.ingest_from_upload(tmp_path, file.filename or "uploaded_video")
        tmp_path.unlink(missing_ok=True)
        return {"message": "Video uploaded and ingested successfully", "video": payload}

    except YoutubeTranscriptUnavailableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except subprocess.CalledProcessError as exc:  # type: ignore[name-defined]
        raise HTTPException(status_code=500, detail=f"External tool failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/videos/{video_id}/summary", response_model=SummaryResponse)
def get_summary(video_id: str) -> SummaryResponse:
    video = metadata_repo.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        summary = artifact_repo.load_json(video_id, "summary.json")
    except FileNotFoundError:
        summary = video.get("summary", {})

    return SummaryResponse(**summary)


@router.get("/videos/{video_id}/transcript")
def get_transcript(video_id: str) -> dict:
    video = metadata_repo.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        chunks = artifact_repo.load_json(video_id, "chunks.json")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Transcript chunks not found") from exc

    return {"video_id": video_id, "chunks": chunks}


@router.post("/videos/{video_id}/qa", response_model=QAResponse)
def ask_question(video_id: str, request: QARequest) -> QAResponse:
    video = metadata_repo.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    response = get_rag_service().answer_question(video, request.question)
    return QAResponse(**response)


@router.post("/videos/{video_id}/search", response_model=TopicSearchResponse)
def topic_search(video_id: str, request: SearchRequest) -> TopicSearchResponse:
    video = metadata_repo.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    response = get_rag_service().topic_search(video, request.query)
    return TopicSearchResponse(**response)


@router.get("/videos/{video_id}/graph", response_model=GraphResponse)
def get_graph(video_id: str) -> GraphResponse:
    video = metadata_repo.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        graph = artifact_repo.load_json(video_id, "graph.json")
    except FileNotFoundError:
        graph = {"nodes": [], "links": []}

    return GraphResponse(**graph)


@router.get("/videos/{video_id}/flashcards", response_model=FlashcardsResponse)
def get_flashcards(video_id: str) -> FlashcardsResponse:
    video = metadata_repo.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        flashcards = artifact_repo.load_json(video_id, "flashcards.json")
    except FileNotFoundError:
        flashcards = []

    return FlashcardsResponse(video_id=video_id, flashcards=flashcards)
