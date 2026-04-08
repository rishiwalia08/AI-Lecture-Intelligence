from __future__ import annotations

import re
from collections import Counter

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
                "answer_type": "not_found",
                "confidence": 0.0,
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
            return {
                "answer": self._fallback_answer(question, references),
                "answer_type": self._answer_type(question, references),
                "confidence": self._confidence_score(question, references),
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

        return {
            "answer": answer,
            "answer_type": self._answer_type(question, references),
            "confidence": self._confidence_score(question, references),
            "references": references,
        }

    def _fallback_answer(self, question: str, references: list[dict]) -> str:
        q = (question or "").strip().lower()
        top_text = (references[0].get("text") or "").strip() if references else ""
        all_text = " ".join((r.get("text") or "") for r in references[:8]).strip()
        all_text_lower = all_text.lower()

        if not top_text:
            return "I found transcript matches, but the text is too weak to give a reliable answer."

        # Accent / language questions are not reliably answerable from text alone.
        if re.search(r"accent|voice|pronunciation|speak|spoken|speaker", q):
            language_hint = self._detect_language_hint(all_text_lower)
            if language_hint:
                return (
                    f"I can’t reliably identify accent from transcript text alone, but the speech appears to be mixed {language_hint}."
                )
            return (
                "I can’t reliably identify the accent from transcript text alone. If you want, I can infer the likely language or summarize the speech style instead."
            )

        # Intent: user asks what the video is about.
        if re.search(r"what.*(video|lecture).*(about)|summary|main point|topic", q):
            topic = self._infer_topic(all_text_lower, top_text)
            return (
                f"This video appears to be about {topic}. "
                f"(based on transcript evidence around {references[0]['timestamp']})."
            )

        # Intent: user asks who is featured/shown.
        if re.search(r"\b(who|featuring|featured|shown|starring)\b", q):
            person_answer = self._extract_person_answer(all_text)
            if person_answer:
                return f"{person_answer} (evidence: {references[0]['timestamp']})."
            return (
                "I could not find a clearly named person in the retrieved transcript context."
            )

        # Intent: specific factual / explanatory question.
        best_sentence = self._best_matching_sentence(question, all_text)
        if best_sentence:
            return (
                f"From the transcript: {best_sentence} "
                f"(evidence: {references[0]['timestamp']})."
            )

        # Intent: user asks about drink/beverage.
        if re.search(r"drink|beverage|coffee|tea|milk|juice|water", q):
            beverage = self._detect_beverage(all_text_lower)
            if beverage:
                return (
                    f"The drink being discussed is {beverage}. "
                    f"Evidence appears around {references[0]['timestamp']}."
                )
            return (
                "I can see conversation text, but I cannot confidently identify the exact drink from transcript evidence alone."
            )

        topic = self._infer_topic(all_text_lower, top_text)
        return (
            f"Based on the transcript, the video seems to be about {topic}. "
            f"(evidence: {references[0]['timestamp']})."
        )

    def _first_sentence(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", (text or "").strip())
        if not cleaned:
            return "evidence is weak."
        sentence = re.split(r"(?<=[.!?])\s+", cleaned, maxsplit=1)[0]
        if len(sentence) > 180:
            sentence = sentence[:180].rstrip() + "..."
        return sentence

    def _infer_topic(self, text: str, fallback: str) -> str:
        keyword_map = [
            ("railway maintenance on a mountain line", ["railway", "track", "trolley", "bridge", "train", "sleeper", "blasting", "inspection"]),
            ("a mountain railway engineering/maintenance job", ["engineering", "section engineer", "maintenance", "track", "inspection", "bridge"]),
            ("a conversation about drinks or refreshments", ["coffee", "tea", "milk", "drink", "cup"]),
        ]
        for label, keywords in keyword_map:
            score = sum(1 for k in keywords if k in text)
            if score >= 2:
                return label

        words = [w for w in re.findall(r"[a-z]+", text) if len(w) > 4]
        common = [w for w, _ in Counter(words).most_common(4) if w not in {"there", "which", "about", "video", "these", "those"}]
        if common:
            return ", ".join(common)
        return self._first_sentence(fallback)

    def _extract_person_answer(self, text: str) -> str | None:
        cleaned = re.sub(r"\s+", " ", text or "").strip()
        if not cleaned:
            return None

        # Pattern: role + person name (common in your transcripts)
        m = re.search(
            r"\b(section engineer|engineer|inspector|worker|officer)\s+([a-z][a-z]+\s+[a-z][a-z]+)\b",
            cleaned,
            flags=re.IGNORECASE,
        )
        if m:
            role = m.group(1).strip().title()
            name = " ".join(w.capitalize() for w in m.group(2).split())
            return f"The video features {name} ({role})."

        # Fallback: two-word name candidates
        candidates = re.findall(r"\b([a-z][a-z]+\s+[a-z][a-z]+)\b", cleaned, flags=re.IGNORECASE)
        blacklist = {
            "mountain railway",
            "section engineer",
            "natural calamity",
            "quick decision",
            "younger person",
        }
        for cand in candidates:
            c = cand.lower().strip()
            if c in blacklist:
                continue
            if any(tok in c for tok in ["railway", "track", "bridge", "train", "engineer", "section"]):
                continue
            name = " ".join(w.capitalize() for w in cand.split())
            return f"The video appears to feature {name}."

        return None

    def _best_matching_sentence(self, question: str, text: str) -> str | None:
        q_tokens = self._content_tokens(question)
        if not q_tokens:
            return None

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s.strip()]
        if not sentences:
            return None

        best_sentence = ""
        best_score = 0.0

        for s in sentences:
            s_tokens = self._content_tokens(s)
            if not s_tokens:
                continue

            overlap = len(set(q_tokens) & set(s_tokens))
            # Light boost for explanatory cues.
            cue_boost = 0.0
            sl = s.lower()
            if any(w in question.lower() for w in ["how", "why"]) and any(c in sl for c in ["because", "so", "therefore", "challenging", "dangerous"]):
                cue_boost = 0.6
            score = overlap + cue_boost + min(len(s_tokens), 24) / 100.0

            if score > best_score:
                best_score = score
                best_sentence = s

        if best_score < 1.0:
            return None

        cleaned = re.sub(r"\s+", " ", best_sentence).strip()
        if len(cleaned) > 220:
            cleaned = cleaned[:220].rstrip() + "..."
        return cleaned

    def _content_tokens(self, text: str) -> list[str]:
        stop = {
            "the", "is", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "it",
            "this", "that", "these", "those", "video", "about", "what", "which", "who", "when",
            "where", "why", "how", "from", "are", "was", "were", "be", "been", "being", "we",
            "you", "they", "he", "she", "i", "my", "our", "your", "their", "do", "does", "did",
            "can", "could", "would", "should", "at", "by", "as", "if", "then", "than",
        }
        tokens = re.findall(r"[a-zA-Z][a-zA-Z'-]{1,}", (text or "").lower())
        return [t for t in tokens if t not in stop and len(t) > 2]

    def _detect_language_hint(self, text: str) -> str | None:
        hindi_markers = [" hai ", " mein ", " ki ", " ka ", " nahi ", " aur ", " kya ", " hum ", " aap "]
        english_markers = ["the ", "and ", "with ", "this ", "that "]
        hindi_score = sum(marker in f" {text} " for marker in hindi_markers)
        english_score = sum(marker in f" {text} " for marker in english_markers)
        if hindi_score >= 2:
            return "Hindi and English"
        if english_score >= 3:
            return "English"
        return None

    def _answer_type(self, question: str, references: list[dict]) -> str:
        q = (question or "").lower()
        if re.search(r"what.*(video|lecture).*(about)|summary|main point|topic", q):
            return "summary"
        if re.search(r"\b(who|featuring|featured|shown|starring)\b", q):
            return "person"
        if re.search(r"accent|voice|pronunciation|speak|spoken|speaker", q):
            return "language_or_voice"
        if re.search(r"who|when|where|which|what", q):
            return "factual"
        if references:
            return "grounded"
        return "uncertain"

    def _confidence_score(self, question: str, references: list[dict]) -> float:
        q = (question or "").lower()
        if not references:
            return 0.0
        score = 0.35
        if len(references) >= 3:
            score += 0.2
        ref_text = " ".join((r.get("text") or "") for r in references[:6])
        best = self._best_matching_sentence(question, ref_text)
        if best:
            score += 0.15
        if re.search(r"what.*(video|lecture).*(about)|summary|main point|topic", q):
            score += 0.15
        if re.search(r"accent|voice|pronunciation|speak|spoken|speaker", q):
            score -= 0.2
        if re.search(r"coffee|tea|milk|water|drink", q):
            score += 0.1
        return max(0.0, min(1.0, round(score, 2)))

    def _detect_beverage(self, text: str) -> str | None:
        candidates = [
            "coffee",
            "tea",
            "milk",
            "water",
            "juice",
            "cold drink",
            "soda",
        ]
        for c in candidates:
            if re.search(rf"\b{re.escape(c)}\b", text):
                return c
        return None

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
