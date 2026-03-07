"""
src/services/retrieval_service.py
-----------------------------------
Unified retrieval pipeline for the Speech RAG system — Phase 4.

Wires together all Phase 3 and Phase 4 components into a single callable:

    user query (text or audio)
        │
        ▼
    QueryProcessor.process()
        │
        ▼
    Embedder.embed_query()
        │
        ├─▶ ChromaDB semantic search ──┐
        │                              ├─▶ RRF merge (HybridSearcher)
        └─▶ BM25 keyword search ───────┘
                                        │
                                        ▼
                                    Reranker.rerank()
                                        │
                                        ▼
                              top-N results + metrics CSV

Usage
-----
    from src.services.retrieval_service import RetrievalService, ServiceConfig

    svc     = RetrievalService.from_config("config/config.yaml")
    results = svc.retrieve_context("What is gradient descent?")
    for r in results:
        print(r["timestamp"], r["text"][:80])
"""

from __future__ import annotations

import csv
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.embedding.chunking import Chunk, load_chunks
from src.embedding.embedder import Embedder, EmbedderConfig
from src.retrieval.hybrid_search import HybridConfig, HybridSearcher
from src.retrieval.metadata_builder import format_timestamp
from src.retrieval.query_processor import QueryProcessor, QueryProcessorConfig
from src.retrieval.reranker import Reranker, RerankerConfig
from src.vectorstore.chroma_manager import ChromaConfig, ChromaManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────
@dataclass
class ServiceConfig:
    """
    Top-level configuration for :class:`RetrievalService`.

    Attributes
    ----------
    embedder_cfg : EmbedderConfig
    chroma_cfg : ChromaConfig
    hybrid_cfg : HybridConfig
    reranker_cfg : RerankerConfig
    qp_cfg : QueryProcessorConfig
    chunks_dir : Path
        Directory containing ``*_chunks.json`` files for BM25 index.
    metrics_path : Path
        CSV file where per-query metrics are appended.
    """
    embedder_cfg:  EmbedderConfig       = field(default_factory=EmbedderConfig)
    chroma_cfg:    ChromaConfig         = field(default_factory=ChromaConfig)
    hybrid_cfg:    HybridConfig         = field(default_factory=HybridConfig)
    reranker_cfg:  RerankerConfig       = field(default_factory=RerankerConfig)
    qp_cfg:        QueryProcessorConfig = field(default_factory=QueryProcessorConfig)
    chunks_dir:    Path                 = Path("data/chunks")
    metrics_path:  Path                 = Path("logs/retrieval_metrics.csv")

    @classmethod
    def from_yaml(cls, config_path: str | Path, project_root: Path | None = None) -> "ServiceConfig":
        """
        Build a ``ServiceConfig`` from ``config/config.yaml``.

        Parameters
        ----------
        config_path : str | Path
        project_root : Path, optional
            Used to resolve relative paths. Defaults to CWD.
        """
        root = project_root or Path.cwd()
        with open(config_path) as fh:
            raw = yaml.safe_load(fh)

        retrieval = raw.get("retrieval", {})

        embedder_cfg = EmbedderConfig(
            model_name=raw.get("embedding_model", "BAAI/bge-m3"),
            batch_size=raw.get("embedding_batch_size", 32),
        )
        chroma_cfg = ChromaConfig(
            db_path=str(root / raw.get("vector_db_path", "vector_db")),
            collection_name=raw.get("vector_collection", "lecture_index"),
        )
        hybrid_cfg = HybridConfig(
            semantic_top_k=retrieval.get("semantic_top_k", 10),
            bm25_top_k=retrieval.get("bm25_top_k", 10),
            rrf_k=retrieval.get("rrf_k", 60),
            max_candidates=retrieval.get("max_candidates", 20),
        )
        reranker_cfg = RerankerConfig(
            model_name=raw.get("reranker_model", "BAAI/bge-reranker-large"),
            top_n=retrieval.get("final_results", 5),
        )
        return cls(
            embedder_cfg=embedder_cfg,
            chroma_cfg=chroma_cfg,
            hybrid_cfg=hybrid_cfg,
            reranker_cfg=reranker_cfg,
            chunks_dir=root / raw.get("chunks_path", "data/chunks"),
            metrics_path=root / raw.get("retrieval_metrics_path", "logs/retrieval_metrics.csv"),
        )


# ──────────────────────────────────────────────────────────────
# Metrics helpers
# ──────────────────────────────────────────────────────────────
_METRICS_COLS = [
    "timestamp_utc", "raw_query", "cleaned_query",
    "num_candidates", "final_results", "query_time_s",
]


def _init_metrics_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=_METRICS_COLS).writeheader()


def _append_metrics(path: Path, row: Dict[str, Any]) -> None:
    with path.open("a", newline="", encoding="utf-8") as fh:
        csv.DictWriter(fh, fieldnames=_METRICS_COLS).writerow(row)


# ──────────────────────────────────────────────────────────────
# Speech transcription helper
# ──────────────────────────────────────────────────────────────
def _transcribe_audio(audio_path: str | Path) -> str:
    """
    Convert audio input to text using openai-whisper (already in requirements).

    Parameters
    ----------
    audio_path : str | Path

    Returns
    -------
    str
        Transcribed text from the audio file.
    """
    try:
        import whisper  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "openai-whisper is not installed. Run: pip install openai-whisper"
        ) from exc

    logger.info("Transcribing audio query: '%s'", audio_path)
    model  = whisper.load_model("base")
    result = model.transcribe(str(audio_path))
    text   = result.get("text", "").strip()
    logger.info("Audio query transcribed: '%s'", text)
    return text


# ──────────────────────────────────────────────────────────────
# Retrieval Service
# ──────────────────────────────────────────────────────────────
class RetrievalService:
    """
    Unified retrieval pipeline for the Interactive Lecture Intelligence system.

    Parameters
    ----------
    config : ServiceConfig
    """

    def __init__(self, config: Optional[ServiceConfig] = None) -> None:
        self.config = config or ServiceConfig()
        self._built = False

        # Sub-components (instantiated eagerly, models loaded lazily)
        self._qp      = QueryProcessor(self.config.qp_cfg)
        self._embedder = Embedder(self.config.embedder_cfg)
        self._manager  = ChromaManager(self.config.chroma_cfg)
        self._searcher = HybridSearcher(
            chroma_manager=self._manager,
            embedder=self._embedder,
            config=self.config.hybrid_cfg,
        )
        self._reranker = Reranker(self.config.reranker_cfg)

        _init_metrics_csv(self.config.metrics_path)
        logger.info("RetrievalService initialised.")

    @classmethod
    def from_config(cls, config_path: str | Path) -> "RetrievalService":
        """Convenience factory — load config from YAML."""
        cfg = ServiceConfig.from_yaml(config_path)
        return cls(cfg)

    # ──────────────────────────────────────────────────────────
    # BM25 index construction
    # ──────────────────────────────────────────────────────────
    def build_bm25_index(self, chunks: Optional[List[Any]] = None) -> None:
        """
        Build (or rebuild) the BM25 index.

        If ``chunks`` is not supplied, all ``*_chunks.json`` files in
        ``config.chunks_dir`` are loaded automatically.
        """
        if chunks is None:
            chunks = self._load_chunks_from_dir(self.config.chunks_dir)

        self._searcher.build_bm25_index(chunks)
        self._built = True
        logger.info("BM25 index built: %d chunks.", len(chunks))

    @staticmethod
    def _load_chunks_from_dir(directory: Path) -> List[Chunk]:
        chunks: List[Chunk] = []
        for path in sorted(directory.glob("*_chunks.json")):
            try:
                chunks.extend(load_chunks(path))
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to load chunks from '%s': %s", path, exc)
        logger.info("Loaded %d chunks from '%s'.", len(chunks), directory)
        return chunks

    # ──────────────────────────────────────────────────────────
    # Core retrieval
    # ──────────────────────────────────────────────────────────
    def retrieve_context(
        self,
        user_query: str,
        input_type: str = "text",
        top_n: Optional[int] = None,
        lecture_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Full retrieval pipeline: process → hybrid search → rerank.

        Parameters
        ----------
        user_query : str
            Raw text query **or** path to an audio file when
            ``input_type="audio"``.
        input_type : str
            ``"text"`` (default) or ``"audio"``.
        top_n : int, optional
            Override ``reranker_cfg.top_n``.
        lecture_filter : str, optional
            Restrict results to a specific ``lecture_id``.

        Returns
        -------
        list[dict]
            Final ranked results, each containing:
            ``text``, ``lecture_id``, ``start_time``, ``end_time``,
            ``timestamp``, ``score``, ``chunk_id``.
        """
        t_start = time.perf_counter()

        # ── Audio transcription ───────────────────────────────
        if input_type == "audio":
            user_query = _transcribe_audio(user_query)

        raw_query = user_query
        logger.info("Retrieval request: '%s'", raw_query[:120])

        # ── Step 1: Query processing ──────────────────────────
        cleaned = self._qp.process(raw_query)
        if not cleaned:
            logger.warning("Query reduced to empty string after processing.")
            return []

        # ── Step 2: Embed query ───────────────────────────────
        query_embedding = self._embedder.embed_query(cleaned)

        # ── Step 3: Hybrid search ─────────────────────────────
        where = {"lecture_id": lecture_filter} if lecture_filter else None
        candidates = self._searcher.hybrid_search(
            query_text=cleaned,
            query_embedding=query_embedding,
            where=where,
        )

        # ── Step 4: Rerank ────────────────────────────────────
        final = self._reranker.rerank(cleaned, candidates, top_n=top_n)

        # ── Step 5: Normalise output ──────────────────────────
        results = self._normalise_results(final)

        elapsed = time.perf_counter() - t_start
        logger.info(
            "Retrieved %d results for '%s' in %.3fs.",
            len(results), raw_query[:60], elapsed,
        )

        # ── Metrics logging ───────────────────────────────────
        _append_metrics(self.config.metrics_path, {
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "raw_query":     raw_query[:200],
            "cleaned_query": cleaned[:200],
            "num_candidates": len(candidates),
            "final_results": len(results),
            "query_time_s":  round(elapsed, 4),
        })

        return results

    # ──────────────────────────────────────────────────────────
    # Normalisation
    # ──────────────────────────────────────────────────────────
    @staticmethod
    def _normalise_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ensure every result has the canonical output schema."""
        out = []
        for r in results:
            start = float(r.get("start_time", 0.0))
            out.append({
                "text":       r.get("text", ""),
                "lecture_id": r.get("lecture_id", "unknown"),
                "start_time": start,
                "end_time":   float(r.get("end_time", 0.0)),
                "timestamp":  r.get("timestamp") or format_timestamp(start),
                "score":      round(float(r.get("rerank_score", r.get("rrf_score", 0.0))), 4),
                "chunk_id":   r.get("chunk_id", ""),
            })
        return out
