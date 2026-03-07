"""
src/retrieval/query_processor.py
----------------------------------
Query cleaning and normalisation for the Speech RAG retrieval pipeline — Phase 4.

Produces a cleaned query string suitable for both BM25 keyword matching and
semantic embedding without polluting the representation with noise words.

Cleaning steps (in order)
--------------------------
1. Unicode normalise (NFKC) and strip leading/trailing whitespace.
2. Lower-case.
3. Remove URLs.
4. Remove punctuation (keep hyphens inside words, e.g. "bi-gram").
5. Collapse multiple whitespace → single space.
6. Remove English stopwords (built-in list — no NLTK download required).
7. Discard tokens shorter than ``min_token_length``.

Usage
-----
    from src.retrieval.query_processor import QueryProcessor, process_query

    # Convenience function (default config)
    clean = process_query("What exactly IS the KMP algorithm used for?")
    # → "kmp algorithm used"

    # Custom config
    proc  = QueryProcessor(QueryProcessorConfig(remove_stopwords=False))
    clean = proc.process("Hello, world!")
    # → "hello world"
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import FrozenSet, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────
# Built-in English stopword list
# ──────────────────────────────────────────────────────────────
_DEFAULT_STOPWORDS: FrozenSet[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "about", "into", "through", "during",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "shall", "may",
    "might", "must", "can", "need", "dare", "ought", "used",
    "i", "me", "my", "we", "our", "ours", "you", "your", "he", "him", "his",
    "she", "her", "it", "its", "they", "them", "their",
    "this", "that", "these", "those", "what", "which", "who", "whom", "how",
    "when", "where", "why", "all", "each", "every", "both", "few", "more",
    "most", "some", "any", "no", "not", "only", "same", "so", "than",
    "too", "very", "just", "because", "as", "until", "while", "although",
    "if", "then", "else", "also", "well", "s", "t", "d", "re", "ve", "ll",
    "exactly", "please", "tell", "explain", "describe", "give", "show",
})

# Regex compiled once at module load
_URL_RE     = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_PUNCT_RE   = re.compile(r"(?<!\w)-|-(?!\w)|[^\w\s-]")
_SPACE_RE   = re.compile(r"\s+")


# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
@dataclass
class QueryProcessorConfig:
    """
    Configuration for :class:`QueryProcessor`.

    Attributes
    ----------
    remove_stopwords : bool
        If True, remove common English stopwords after tokenisation.
    lowercase : bool
        If True, convert query to lowercase.
    min_token_length : int
        Discard tokens shorter than this (e.g. single-char artifacts).
    extra_stopwords : list[str]
        Additional domain-specific stopwords to remove.
    """
    remove_stopwords: bool = True
    lowercase: bool = True
    min_token_length: int = 2
    extra_stopwords: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# Processor class
# ──────────────────────────────────────────────────────────────
class QueryProcessor:
    """
    Cleans and normalises a raw user query for retrieval.

    Parameters
    ----------
    config : QueryProcessorConfig, optional
        Processing configuration. Defaults to ``QueryProcessorConfig()``.
    """

    def __init__(self, config: Optional[QueryProcessorConfig] = None) -> None:
        self.config = config or QueryProcessorConfig()
        self._stopwords: FrozenSet[str] = _DEFAULT_STOPWORDS | frozenset(
            w.lower() for w in self.config.extra_stopwords
        )

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────
    def process(self, raw_query: str) -> str:
        """
        Clean and normalise a raw query string.

        Parameters
        ----------
        raw_query : str
            The user's original question or search string.

        Returns
        -------
        str
            The cleaned, space-separated token string. Returns an empty
            string if the query contained no usable tokens.
        """
        if not raw_query or not raw_query.strip():
            logger.debug("QueryProcessor received empty query.")
            return ""

        # Step 1 — unicode normalise
        text = unicodedata.normalize("NFKC", raw_query).strip()

        # Step 2 — lowercase
        if self.config.lowercase:
            text = text.lower()

        # Step 3 — remove URLs
        text = _URL_RE.sub(" ", text)

        # Step 4 — remove punctuation (keep intra-word hyphens)
        text = _PUNCT_RE.sub(" ", text)

        # Step 5 — collapse whitespace
        text = _SPACE_RE.sub(" ", text).strip()

        # Step 6 — tokenise and filter
        tokens = text.split()

        if self.config.remove_stopwords:
            tokens = [t for t in tokens if t not in self._stopwords]

        # Step 7 — min token length
        tokens = [t for t in tokens if len(t) >= self.config.min_token_length]

        cleaned = " ".join(tokens)
        logger.debug("Query cleaned: '%s' → '%s'", raw_query, cleaned)
        return cleaned

    def tokenize(self, text: str) -> List[str]:
        """
        Return exactly the token list that ``process()`` would produce.

        Useful for BM25 index building (avoids splitting the cleaned
        string again).
        """
        cleaned = self.process(text)
        return cleaned.split() if cleaned else []


# ──────────────────────────────────────────────────────────────
# Module-level convenience function
# ──────────────────────────────────────────────────────────────
_default_processor = QueryProcessor()


def process_query(raw_query: str) -> str:
    """
    Clean a query using the default :class:`QueryProcessor` configuration.

    Parameters
    ----------
    raw_query : str

    Returns
    -------
    str
        Cleaned query string.

    Examples
    --------
    >>> process_query("What exactly is the KMP algorithm used for?")
    'kmp algorithm'
    """
    return _default_processor.process(raw_query)
