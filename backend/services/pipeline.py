from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from db.repository import ArtifactRepository, MetadataRepository
from services.embeddings import EmbeddingService, VectorStoreService
from services.llm import LLMService
from services.summarizer import SummarizerService
from services.transcription import VideoIngestionService
from services.graph_builder import GraphBuilderService
from services.flashcard_builder import FlashcardBuilderService


class LecturePipeline:
    def __init__(self) -> None:
        self.metadata_repo = MetadataRepository()
        self.artifact_repo = ArtifactRepository()

        self.ingestor = VideoIngestionService()
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStoreService(self.embedding_service)
        self.llm_service = LLMService()
        self.summarizer = SummarizerService(self.llm_service)
        self.graph_builder = GraphBuilderService(self.llm_service)
        self.flashcard_builder = FlashcardBuilderService(self.llm_service)

    def ingest_from_youtube(self, youtube_url: str, title: str | None = None) -> dict:
        video_id = str(uuid4())
        work_dir = self.artifact_repo.video_dir(video_id)

        # On hosted Render environments, YouTube download is frequently blocked.
        # Prefer direct transcript ingestion to keep the web service reliable.
        segments = self.ingestor.fetch_youtube_transcript(youtube_url)

        chunks = self.ingestor.chunk_transcript(segments)

        self.artifact_repo.save_json(video_id, "segments.json", segments)
        self.artifact_repo.save_json(video_id, "chunks.json", chunks)

        self.vector_store.upsert_chunks(video_id, chunks)
        summary = self.summarizer.generate_summary(chunks)
        self.artifact_repo.save_json(video_id, "summary.json", summary)
        
        graph = self.graph_builder.build_graph(chunks)
        self.artifact_repo.save_json(video_id, "graph.json", graph)
        
        flashcards = self.flashcard_builder.build_flashcards(chunks)
        self.artifact_repo.save_json(video_id, "flashcards.json", flashcards)

        payload = {
            "video_id": video_id,
            "source_type": "youtube",
            "youtube_url": youtube_url,
            "title": title or "YouTube Lecture",
            "chunk_count": len(chunks),
            "status": "ready",
            "summary": summary,
        }
        self.metadata_repo.create_video(payload)
        return payload

    def ingest_from_upload(self, upload_path: Path, original_filename: str) -> dict:
        video_id = str(uuid4())
        work_dir = self.artifact_repo.video_dir(video_id)

        extension = upload_path.suffix or ".mp4"
        stored_video = work_dir / f"source{extension}"
        shutil.copyfile(upload_path, stored_video)

        audio_path = self.ingestor.extract_audio(stored_video, work_dir)
        segments = self.ingestor.transcribe_audio(audio_path)
        chunks = self.ingestor.chunk_transcript(segments)

        self.artifact_repo.save_json(video_id, "segments.json", segments)
        self.artifact_repo.save_json(video_id, "chunks.json", chunks)

        self.vector_store.upsert_chunks(video_id, chunks)
        summary = self.summarizer.generate_summary(chunks)
        self.artifact_repo.save_json(video_id, "summary.json", summary)

        graph = self.graph_builder.build_graph(chunks)
        self.artifact_repo.save_json(video_id, "graph.json", graph)
        
        flashcards = self.flashcard_builder.build_flashcards(chunks)
        self.artifact_repo.save_json(video_id, "flashcards.json", flashcards)

        payload = {
            "video_id": video_id,
            "source_type": "upload",
            "youtube_url": None,
            "title": original_filename,
            "chunk_count": len(chunks),
            "status": "ready",
            "summary": summary,
        }
        self.metadata_repo.create_video(payload)
        return payload
