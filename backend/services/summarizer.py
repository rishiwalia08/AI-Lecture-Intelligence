from __future__ import annotations

from collections import Counter

from services.llm import LLMService


class SummarizerService:
    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service

    def _fallback_summary(self, chunks: list[dict]) -> dict:
        texts = [c["text"] for c in chunks[:12]]
        joined = " ".join(texts)

        words = [w.lower().strip(".,!?()[]{}\"'`") for w in joined.split() if len(w) > 4]
        common = [w for w, _ in Counter(words).most_common(8)]

        topic_blocks = []
        for c in chunks[:8]:
            topic_blocks.append(
                {
                    "topic": c["text"][:70] + "..." if len(c["text"]) > 70 else c["text"],
                    "start_time": c["start_time"],
                    "end_time": c["end_time"],
                }
            )

        return {
            "tldr": texts[0][:240] + "..." if texts else "No content found.",
            "detailed_notes": joined[:2000],
            "key_points": common,
            "topic_breakdown": topic_blocks,
        }

    def generate_summary(self, chunks: list[dict]) -> dict:
        if not chunks:
            return {
                "tldr": "No transcript available.",
                "detailed_notes": "",
                "key_points": [],
                "topic_breakdown": [],
            }

        if not self.llm.available():
            return self._fallback_summary(chunks)

        context = "\n\n".join(
            f"[{i}] ({c['start_time']:.2f}-{c['end_time']:.2f}) {c['text']}"
            for i, c in enumerate(chunks[:120])
        )

        system_prompt = (
            "You summarize lecture transcripts. Return strict JSON with keys: "
            "tldr (string), detailed_notes (string), key_points (array of strings), "
            "topic_breakdown (array of objects with topic, start_time, end_time)."
        )
        user_prompt = (
            "Summarize the following transcript chunks. Keep factual grounding in transcript only.\n\n"
            f"{context}"
        )

        raw = self.llm.chat(system_prompt, user_prompt)

        # Light guard for non-JSON responses
        import json

        try:
            return json.loads(raw)
        except Exception:
            return self._fallback_summary(chunks)
