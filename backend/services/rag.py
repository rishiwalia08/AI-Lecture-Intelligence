from __future__ import annotations

from services.llm import LLMService
from services.embeddings import VectorStoreService
from utils.time_utils import timestamp_range
from utils.video_utils import youtube_timestamp_link


class RAGService:
    def __init__(self, llm_service: LLMService, vector_store: VectorStoreService) -> None:
        self.llm = llm_service
        self.vector_store = vector_store

    def answer_question(self, video: dict, question: str) -> dict:
        hits = self.vector_store.semantic_search(video["video_id"], question)
        if not hits:
            return {
                "answer": "I could not find relevant content in this transcript.",
                "references": [],
            }

        references = [
            {
                "chunk_id": h["chunk_id"],
                "text": h["text"],
                "start_time": h["start_time"],
                "end_time": h["end_time"],
                "timestamp": timestamp_range(h["start_time"], h["end_time"]),
                "youtube_link": youtube_timestamp_link(video.get("youtube_url"), h["start_time"]),
            }
            for h in hits
        ]

        if not self.llm.available():
            stitched = "\n".join(
                f"- {ref['timestamp']}: {ref['text'][:220]}"
                for ref in references[:4]
            )
            return {
                "answer": "Based on the lecture transcript, here are the most relevant sections:\n"
                + stitched,
                "references": references,
            }

        context = "\n\n".join(
            f"[{i}] ({r['start_time']:.2f}-{r['end_time']:.2f}) {r['text']}"
            for i, r in enumerate(references)
        )
        prompt = (
            "Answer the user question using ONLY the context. "
            "If evidence is weak, say so clearly. Provide concise explanation grounded in context. "
            "Do not invent facts.\n\n"
            f"Question: {question}\n\n"
            f"Context:\n{context}"
        )
        answer = self.llm.chat(
            "You are a retrieval-augmented lecture assistant. Always stay grounded in transcript evidence.",
            prompt,
            temperature=0.0,
        )

        return {"answer": answer, "references": references}

    def topic_search(self, video: dict, query: str) -> dict:
        hits = self.vector_store.semantic_search(video["video_id"], query)
        references = [
            {
                "chunk_id": h["chunk_id"],
                "text": h["text"],
                "start_time": h["start_time"],
                "end_time": h["end_time"],
                "timestamp": timestamp_range(h["start_time"], h["end_time"]),
                "youtube_link": youtube_timestamp_link(video.get("youtube_url"), h["start_time"]),
            }
            for h in hits
        ]

        explanation = (
            f"Found {len(references)} relevant transcript sections for '{query}'."
            if references
            else "No strongly related sections found."
        )
        return {"query": query, "explanation": explanation, "results": references}
