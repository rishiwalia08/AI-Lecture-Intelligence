"""
src/llm/rag_prompt.py
-----------------------
Prompt construction for the Speech RAG pipeline — Phase 5.

Implements a strict grounded prompt that instructs the LLM to:
  - Answer ONLY from the provided context.
  - Cite ``lecture_id`` and timestamp for every claim.
  - Refuse (not hallucinate) if the answer is absent from context.

Usage
-----
    from src.llm.rag_prompt import PromptBuilder

    builder  = PromptBuilder()
    messages = builder.build_messages(
        query  = "What is backpropagation?",
        chunks = retrieved_chunks,   # list[dict] from RetrievalService
    )
    response = llm_provider.generate(messages)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# System prompt
# ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT: str = """You are an academic assistant for computer science lectures.

Your role is to help students understand concepts explained in lecture recordings.

STRICT RULES:
1. Answer the user's question using ONLY the provided lecture context below.
2. Do NOT use any external knowledge or assumptions beyond what is in the context.
3. If the answer cannot be found in the provided context, respond EXACTLY with:
   "I cannot find the answer in the lecture material."
4. Always cite your sources. After your answer, list which lecture(s) and
   timestamp(s) contain the relevant information.
5. Keep answers concise and academically precise.
6. If multiple chunks are relevant, synthesise them coherently."""

# Exact string the LLM must return when context is insufficient
CANNOT_FIND_PHRASE: str = "I cannot find the answer in the lecture material."

# Returned immediately when retrieval produces no chunks (LLM not called)
NO_MATERIAL_FOUND: str = "No relevant lecture segment found."


# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
@dataclass
class PromptConfig:
    """
    Configuration for :class:`PromptBuilder`.

    Attributes
    ----------
    max_context_chunks : int
        Maximum number of retrieved chunks to include in the prompt.
        Keeps prompt within token budget.
    max_chunk_chars : int
        Truncate individual chunk text to this many characters.
    include_timestamps : bool
        Whether to include ``[HH:MM:SS – HH:MM:SS]`` in the context block.
    system_prompt : str
        Override the default system prompt.
    """
    max_context_chunks: int = 5
    max_chunk_chars:    int = 800
    include_timestamps: bool = True
    system_prompt:      str = SYSTEM_PROMPT


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def _seconds_to_mmss(seconds: float) -> str:
    """Convert float seconds to ``MM:SS`` string."""
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


def _format_chunk(chunk: Dict[str, Any], index: int, include_timestamps: bool, max_chars: int) -> str:
    """
    Render a single chunk as a labelled context block.

    Example output::

        [Source 1] lecture_07 @ 14:02 – 14:20
        Backpropagation is a method used to update neural network weights…
    """
    lecture_id = chunk.get("lecture_id", "unknown")
    text       = chunk.get("text", "").strip()

    # Truncate
    if len(text) > max_chars:
        text = text[:max_chars] + " …"

    if include_timestamps:
        start = chunk.get("start_time", 0.0)
        end   = chunk.get("end_time",   0.0)
        ts    = f"@ {_seconds_to_mmss(float(start))} – {_seconds_to_mmss(float(end))}"
    else:
        ts = ""

    header = f"[Source {index}] {lecture_id} {ts}".strip()
    return f"{header}\n{text}"


# ──────────────────────────────────────────────────────────────
# PromptBuilder
# ──────────────────────────────────────────────────────────────
class PromptBuilder:
    """
    Assembles the RAG prompt from retrieved chunks and a user query.

    Parameters
    ----------
    config : PromptConfig, optional
    """

    def __init__(self, config: Optional[PromptConfig] = None) -> None:
        self.config = config or PromptConfig()

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────
    def build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Format a list of retrieved chunks into a numbered context block.

        Parameters
        ----------
        chunks : list[dict]
            Each dict must have at minimum ``"text"``, ``"lecture_id"``,
            ``"start_time"``, ``"end_time"`` keys (as returned by
            :meth:`~src.services.retrieval_service.RetrievalService.retrieve_context`).

        Returns
        -------
        str
            Multi-line formatted context string, or empty string if no chunks.
        """
        selected = chunks[: self.config.max_context_chunks]
        if not selected:
            return ""

        parts = [
            _format_chunk(
                c, i + 1,
                self.config.include_timestamps,
                self.config.max_chunk_chars,
            )
            for i, c in enumerate(selected)
        ]
        return "\n\n".join(parts)

    def build_prompt(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """
        Build the full text prompt (for non-chat completions APIs).

        Parameters
        ----------
        query : str
        chunks : list[dict]

        Returns
        -------
        str
            Formatted prompt string with context, question, and "Answer:" header.
        """
        context = self.build_context(chunks)
        prompt  = (
            f"Context:\n{context}\n\n"
            f"Question:\n{query}\n\n"
            f"Answer:"
        )
        logger.debug("Prompt built: %d chars, %d sources.", len(prompt), len(chunks))
        return prompt

    def build_messages(
        self,
        query:  str,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """
        Build a chat-style messages list for chat completion APIs.

        Returns
        -------
        list[dict]
            ``[{"role": "system", "content": ...}, {"role": "user", "content": ...}]``
        """
        context      = self.build_context(chunks)
        user_content = (
            f"Here is the relevant lecture context:\n\n"
            f"{context}\n\n"
            f"Question: {query}"
        )
        messages = [
            {"role": "system", "content": self.config.system_prompt},
            {"role": "user",   "content": user_content},
        ]
        logger.debug(
            "Chat messages built: system=%d chars, user=%d chars.",
            len(self.config.system_prompt), len(user_content),
        )
        return messages

    # ──────────────────────────────────────────────────────────
    # Hallucination guard helpers
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def is_refusal(answer: str) -> bool:
        """Return True if the LLM answered with the standard refusal phrase."""
        return CANNOT_FIND_PHRASE.lower() in answer.lower()

    @staticmethod
    def answer_references_context(answer: str, chunks: List[Dict[str, Any]]) -> bool:
        """
        Heuristic check: does the answer contain at least one word (≥4 chars)
        that also appears in the retrieved context?

        This is a lightweight grounding check — not a full NLI verifier.
        Returns True if the answer appears to draw from the context,
        False if it seems entirely disconnected.
        """
        if not chunks:
            return False

        context_words = set()
        for c in chunks:
            for word in c.get("text", "").lower().split():
                if len(word) >= 4:
                    context_words.add(word.strip(".,;:!?\"'"))

        answer_words = {
            w.strip(".,;:!?\"'")
            for w in answer.lower().split()
            if len(w) >= 4
        }
        overlap = answer_words & context_words
        logger.debug(
            "Grounding check: %d answer words, %d context words, %d overlap.",
            len(answer_words), len(context_words), len(overlap),
        )
        return len(overlap) > 0
