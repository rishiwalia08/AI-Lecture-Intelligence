from __future__ import annotations

from typing import Any

import chromadb
from openai import OpenAI
from sentence_transformers import SentenceTransformer

from config import settings


class EmbeddingService:
    def __init__(self) -> None:
        self.backend = settings.embed_backend
        self._sentence_model: SentenceTransformer | None = None
        self._openai_client: OpenAI | None = None

    def _get_sentence_model(self) -> SentenceTransformer:
        if self._sentence_model is None:
            self._sentence_model = SentenceTransformer(settings.sentence_transformer_model)
        return self._sentence_model

    def _get_openai_client(self) -> OpenAI:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings backend")
        if self._openai_client is None:
            self._openai_client = OpenAI(api_key=settings.openai_api_key)
        return self._openai_client

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self.backend == "openai":
            client = self._get_openai_client()
            response = client.embeddings.create(model=settings.openai_embedding_model, input=texts)
            return [d.embedding for d in response.data]

        model = self._get_sentence_model()
        vectors = model.encode(texts, normalize_embeddings=True)
        return vectors.tolist()

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]


class VectorStoreService:
    def __init__(self, embedding_service: EmbeddingService) -> None:
        chroma_path = settings.data_dir / settings.chroma_dir_name
        chroma_path.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(chroma_path))
        self.embedding_service = embedding_service

    def _collection_name(self, video_id: str) -> str:
        return f"video_{video_id.replace('-', '_')}"

    def upsert_chunks(self, video_id: str, chunks: list[dict[str, Any]]) -> None:
        if not chunks:
            return

        texts = [c["text"] for c in chunks]
        vectors = self.embedding_service.embed_texts(texts)

        collection = self.client.get_or_create_collection(name=self._collection_name(video_id))

        collection.upsert(
            ids=[c["chunk_id"] for c in chunks],
            documents=texts,
            embeddings=vectors,
            metadatas=[
                {
                    "video_id": video_id,
                    "start_time": float(c["start_time"]),
                    "end_time": float(c["end_time"]),
                }
                for c in chunks
            ],
        )

    def semantic_search(self, video_id: str, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        k = top_k or settings.top_k_retrieval
        collection = self.client.get_or_create_collection(name=self._collection_name(video_id))

        qvec = self.embedding_service.embed_query(query)
        res = collection.query(query_embeddings=[qvec], n_results=k)

        documents = res.get("documents", [[]])[0]
        metadatas = res.get("metadatas", [[]])[0]
        distances = res.get("distances", [[]])[0]
        ids = res.get("ids", [[]])[0]

        out: list[dict[str, Any]] = []
        for idx, doc in enumerate(documents):
            meta = metadatas[idx] if idx < len(metadatas) else {}
            out.append(
                {
                    "chunk_id": ids[idx] if idx < len(ids) else f"idx_{idx}",
                    "text": doc,
                    "start_time": meta.get("start_time", 0.0),
                    "end_time": meta.get("end_time", 0.0),
                    "score": distances[idx] if idx < len(distances) else None,
                }
            )
        return out
