from __future__ import annotations

import json
import os
import re
import tempfile
import base64
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import yaml

from backend.services.rag_bridge import get_rag_bridge
from src.asr.timestamp_formatter import format_transcript, save_full_transcript, save_segments
from src.embedding.chunking import ChunkConfig, create_chunks, save_chunks
from src.retrieval.metadata_builder import build_metadata_list
from src.utils.logger import get_logger

logger = get_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _PROJECT_ROOT / "config" / "config.yaml"

_SOURCE_MAP_PATH = _PROJECT_ROOT / "data" / "lecture_sources.json"


def _load_config() -> Dict[str, Any]:
    if not _CONFIG_PATH.exists():
        return {}
    with _CONFIG_PATH.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "lecture"


def _load_source_map() -> Dict[str, str]:
    if not _SOURCE_MAP_PATH.exists():
        return {}
    try:
        with _SOURCE_MAP_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_source_map(data: Dict[str, str]) -> None:
    _SOURCE_MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _SOURCE_MAP_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def attach_video_urls(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    source_map = _load_source_map()
    output: List[Dict[str, Any]] = []
    for src in sources:
        entry = dict(src)
        lecture_id = str(src.get("lecture_id", ""))
        base_url = source_map.get(lecture_id)
        if base_url:
            entry["video_url"] = build_timestamp_url(base_url, float(src.get("start_time", 0.0)))
        output.append(entry)
    return output


def build_timestamp_url(url: str, start_time_s: float) -> str:
    seconds = max(0, int(start_time_s))
    parsed = urlparse(url)

    if "youtube.com" in parsed.netloc or "youtu.be" in parsed.netloc:
        if "youtu.be" in parsed.netloc:
            video_id = parsed.path.strip("/")
            return f"https://www.youtube.com/watch?v={video_id}&t={seconds}s"

        qs = parse_qs(parsed.query)
        qs["t"] = [f"{seconds}s"]
        new_query = urlencode(qs, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    sep = "&" if "?" in url else "?"
    return f"{url}{sep}t={seconds}"


def _ensure_bridge_ready() -> Any:
    bridge = get_rag_bridge()
    if not bridge.ready:
        bridge.initialise()
    if not bridge.ready or bridge._svc is None:
        raise RuntimeError(f"RAG pipeline could not initialize: {bridge.error or 'unknown'}")
    return bridge


def _parse_youtube_video_id(url: str) -> Optional[str]:
    """Extract YouTube video id from common URL formats."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "youtu.be" in host:
        vid = parsed.path.strip("/")
        return vid or None

    if "youtube.com" in host:
        if parsed.path == "/watch":
            vid = parse_qs(parsed.query).get("v", [None])[0]
            return vid
        if parsed.path.startswith("/shorts/"):
            parts = parsed.path.split("/")
            return parts[2] if len(parts) > 2 else None
        if parsed.path.startswith("/embed/"):
            parts = parsed.path.split("/")
            return parts[2] if len(parts) > 2 else None

    return None


def _index_transcript_segments(
    segments: List[Dict[str, Any]],
    lecture_id: str,
    source_url: Optional[str] = None,
    audio_path: str = "",
) -> Dict[str, Any]:
    """Persist transcript, chunk it, index embeddings, and refresh BM25."""
    bridge = _ensure_bridge_ready()
    retrieval = bridge._svc._retrieval

    cfg = _load_config()
    chunk_cfg = ChunkConfig(
        chunk_size=int(cfg.get("chunk_size", 500)),
        chunk_overlap=int(cfg.get("chunk_overlap", 50)),
        min_chunk_tokens=int(cfg.get("min_chunk_tokens", 20)),
    )

    transcript = format_transcript(
        lecture_id=lecture_id,
        segments=segments,
        metadata={
            "source_url": source_url or "",
            "audio_path": audio_path,
        },
    )

    transcripts_dir = _PROJECT_ROOT / cfg.get("transcripts_path", "data/transcripts")
    segments_dir = _PROJECT_ROOT / cfg.get("segments_path", "data/segments")
    chunks_dir = _PROJECT_ROOT / cfg.get("chunks_path", "data/chunks")

    save_full_transcript(transcript, transcripts_dir)
    save_segments(transcript, segments_dir)

    chunks = create_chunks(transcript, chunk_cfg)
    save_chunks(chunks, chunks_dir)

    embeddings = retrieval._embedder.embed_chunks(chunks)
    metadatas = build_metadata_list(chunks)
    indexed = retrieval._manager.upsert(chunks, embeddings, metadatas)
    retrieval.build_bm25_index()

    if source_url:
        source_map = _load_source_map()
        source_map[lecture_id] = source_url
        _save_source_map(source_map)

    return {
        "lecture_id": lecture_id,
        "num_segments": len(segments),
        "num_chunks": len(chunks),
        "indexed_vectors": indexed,
        "duration_s": float(transcript.get("total_duration", 0.0)),
        "message": "Ingestion complete.",
    }


def ingest_local_media(file_path: Path, lecture_id: Optional[str] = None, source_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Transcribe media file, chunk it, embed it, and index into vector DB.
    
    Automatically cleans up the media file after successful transcription.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Media file not found: {file_path}")

    cfg = _load_config()

    try:
        import whisper  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError("openai-whisper is required for media ingest.") from exc

    asr_model_size = str(cfg.get("asr_model_size", "base"))
    asr_language = cfg.get("asr_language", "en")

    logger.info("Ingesting media '%s' with Whisper model=%s", file_path.name, asr_model_size)
    
    try:
        import asyncio
        import time as time_module
        
        # Transcribe with resilient model loading. Some deployments have an
        # older Whisper package that does not recognize newer aliases.
        try:
            model = whisper.load_model(asr_model_size)
        except Exception as model_exc:
            logger.warning(
                "Failed to load Whisper model '%s' (%s). Falling back to 'base'.",
                asr_model_size,
                model_exc,
            )
            model = whisper.load_model("base")
        t0 = time_module.perf_counter()
        
        try:
            result = model.transcribe(str(file_path), language=asr_language)
            elapsed = time_module.perf_counter() - t0
            logger.info("Transcription complete in %.1fs", elapsed)
        except Exception as e:
            logger.error("Transcription failed: %s", e)
            raise RuntimeError(
                f"Transcription failed: {e}. The file may be corrupted or in an unsupported format."
            ) from e
    finally:
        # Delete the uploaded file to free disk space (important on Render free tier)
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info("Deleted media file: %s", file_path)
        except Exception as e:
            logger.warning("Failed to delete media file %s: %s", file_path, e)

    raw_segments = result.get("segments", [])
    segments = [
        {
            "text": str(s.get("text", "")).strip(),
            "start": float(s.get("start", 0.0)),
            "end": float(s.get("end", 0.0)),
        }
        for s in raw_segments
        if str(s.get("text", "")).strip()
    ]
    if not segments:
        raise RuntimeError("No segments produced from media transcription.")

    if lecture_id:
        lecture_id = _slugify(lecture_id)
    else:
        lecture_id = _slugify(file_path.stem)

    return _index_transcript_segments(
        segments=segments,
        lecture_id=lecture_id,
        source_url=source_url,
        audio_path=str(file_path),
    )


def ingest_youtube(url: str, lecture_id: Optional[str] = None) -> Dict[str, Any]:
    """Ingest YouTube using transcript API first, then yt-dlp audio fallback."""
    video_id = _parse_youtube_video_id(url)
    if not video_id:
        raise RuntimeError("Invalid YouTube URL: could not parse video ID.")

    # Preferred path: transcript API (avoids YouTube bot-check download issues)
    transcript_succeeded = False
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore[import]

        transcript_items: List[Dict[str, Any]] = []

        # Try direct convenience API first
        try:
            logger.info("Attempting direct transcript API for video_id=%s", video_id)
            transcript_items = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])
            logger.info("✓ Direct transcript API succeeded (%d items)", len(transcript_items))
        except Exception as direct_exc:
            logger.info("Direct transcript API failed: %s, trying list_transcripts fallback", direct_exc)
            # Fallback to explicit transcript selection (manual/generated/translated)
            try:
                transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
                logger.info("Available transcript kinds: %s", transcripts)
                selected = None
                try:
                    logger.info("Trying find_transcript with ['en', 'en-US', 'en-GB']...")
                    selected = transcripts.find_transcript(["en", "en-US", "en-GB"])
                    logger.info("✓ Manual transcript found")
                except Exception as manual_exc:
                    logger.info("Manual transcript not found: %s, trying generated...", manual_exc)
                    try:
                        logger.info("Trying find_generated_transcript with ['en', 'en-US', 'en-GB']...")
                        selected = transcripts.find_generated_transcript(["en", "en-US", "en-GB"])
                        logger.info("✓ Generated transcript found")
                    except Exception as gen_exc:
                        logger.warning("No generated transcript found: %s", gen_exc)
                        selected = None

                if selected is not None:
                    try:
                        transcript_items = selected.fetch()
                        logger.info("✓ Transcript fetch succeeded (%d items)", len(transcript_items))
                    except Exception as fetch_exc:
                        logger.warning("Transcript fetch failed: %s", fetch_exc)
                        transcript_items = []
            except Exception as list_exc:
                logger.warning("list_transcripts failed: %s", list_exc)
                transcript_items = []

        segments = []
        for item in transcript_items:
            text = str(item.get("text", "")).strip()
            start = float(item.get("start", 0.0))
            duration = float(item.get("duration", 0.0))
            end = start + max(duration, 0.0)
            if text:
                segments.append({"text": text, "start": start, "end": end})

        if segments:
            transcript_succeeded = True
            resolved_lecture_id = _slugify(lecture_id or f"yt_{video_id}")
            logger.info("✓ YouTube transcript API SUCCEEDED for video_id=%s with %d segments", video_id, len(segments))
            return _index_transcript_segments(
                segments=segments,
                lecture_id=resolved_lecture_id,
                source_url=url,
                audio_path="",
            )
        else:
            logger.warning("Transcript API returned 0 segments for video_id=%s", video_id)
    except Exception as transcript_exc:  # noqa: BLE001
        logger.warning("YouTube transcript API failed for %s: %s", video_id, transcript_exc)

    # Fallback path: download audio then transcribe
    logger.info("YouTube transcript API unavailable or returned empty segments. Attempting yt-dlp audio download fallback...")
    try:
        import yt_dlp  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "Could not fetch YouTube transcript and yt-dlp is unavailable for fallback. "
            "Install yt-dlp or use direct file upload ingest."
        ) from exc

    tmp_dir = Path(tempfile.mkdtemp(prefix="yt_ingest_"))
    out_template = str(tmp_dir / "%(id)s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "noplaylist": True,
        "quiet": False,  # Changed to False for better error diagnostics
        "no_warnings": False,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.youtube.com/",
        },
    }

    # Optional cookie support for bot-protected videos in cloud deploys.
    # Set one of:
    # - YTDLP_COOKIES_PATH=/path/to/cookies.txt
    # - YTDLP_COOKIES_B64=<base64-of-cookies.txt>
    cookies_path = os.getenv("YTDLP_COOKIES_PATH", "").strip()
    cookies_b64 = os.getenv("YTDLP_COOKIES_B64", "").strip()
    temp_cookie_file: Optional[Path] = None

    if cookies_path:
        logger.info("Using cookies from file: %s", cookies_path)
        ydl_opts["cookiefile"] = cookies_path
    elif cookies_b64:
        try:
            logger.info("Decoding base64-encoded cookies...")
            decoded = base64.b64decode(cookies_b64.encode("utf-8"))
            temp_cookie_file = tmp_dir / "cookies.txt"
            temp_cookie_file.write_bytes(decoded)
            ydl_opts["cookiefile"] = str(temp_cookie_file)
            logger.info("✓ Cookies loaded from YTDLP_COOKIES_B64")
        except Exception as decode_exc:
            logger.warning("Failed to decode YTDLP_COOKIES_B64: %s", decode_exc)
            temp_cookie_file = None

    info: Dict[str, Any] = {}
    downloaded: Optional[str] = None

    try:
        logger.info("Starting yt-dlp download for video_id=%s with options: %s", video_id, ydl_opts)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded = ydl.prepare_filename(info)
            logger.info("✓ yt-dlp download succeeded, saved to: %s", downloaded)
    except Exception as exc:  # noqa: BLE001
        logger.error("yt-dlp download failed with error: %s", exc, exc_info=True)

        # Final fallback: pytubefix downloader
        try:
            logger.info("Trying pytubefix fallback for video_id=%s", video_id)
            from pytubefix import YouTube  # type: ignore[import]

            yt = YouTube(url)
            stream = (
                yt.streams
                .filter(only_audio=True)
                .order_by("abr")
                .desc()
                .first()
            )
            if stream is None:
                raise RuntimeError("No downloadable audio stream found by pytubefix.")

            downloaded = stream.download(output_path=str(tmp_dir))
            info = {"title": yt.title or "youtube_lecture"}
            logger.info("✓ pytubefix download succeeded, saved to: %s", downloaded)
        except Exception as py_exc:  # noqa: BLE001
            logger.error("pytubefix fallback failed: %s", py_exc, exc_info=True)
            raise RuntimeError(
                "YouTube ingest failed after transcript API + yt-dlp + pytubefix attempts. "
                "This video is strongly bot-protected or unavailable from server-side networks. "
                "Please use Upload+Ingest File, or configure YTDLP_COOKIES_PATH / YTDLP_COOKIES_B64 on Render."
            ) from py_exc
    finally:
        try:
            if temp_cookie_file and temp_cookie_file.exists():
                temp_cookie_file.unlink(missing_ok=True)
        except Exception:
            pass

    if not downloaded:
        raise RuntimeError("No media file downloaded from YouTube.")

    media_path = Path(downloaded)
    title = str(info.get("title", "youtube_lecture"))
    resolved_lecture_id = lecture_id or title

    return ingest_local_media(media_path, lecture_id=resolved_lecture_id, source_url=url)


def get_summaries(limit: int = 20) -> Dict[str, Any]:
    cfg = _load_config()
    transcripts_dir = _PROJECT_ROOT / cfg.get("transcripts_path", "data/transcripts")

    stop = {
        "the", "and", "for", "that", "with", "this", "from", "your", "have", "are", "was",
        "will", "into", "about", "there", "their", "what", "when", "where", "which", "while",
        "then", "than", "also", "into", "using", "used", "they", "them", "you", "our", "can",
        "not", "but", "all", "any", "how", "why", "who", "its", "it", "is", "to", "of", "in",
        "on", "a", "an", "as", "we", "be", "or", "by", "at", "if", "do", "does",
    }

    lectures: List[Dict[str, Any]] = []
    files = sorted(transcripts_dir.glob("*_transcript.json"))[:limit]

    for path in files:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            lecture_id = str(data.get("lecture_id", path.stem.replace("_transcript", "")))
            segments = data.get("segments", [])
            text = " ".join(str(s.get("text", "")) for s in segments)
            words = re.findall(r"[a-zA-Z][a-zA-Z\-]{2,}", text.lower())
            topic_counts = Counter(w for w in words if w not in stop)
            key_topics = [w for w, _ in topic_counts.most_common(8)]

            summary_segments = [str(s.get("text", "")).strip() for s in segments[:8]]
            summary = " ".join(x for x in summary_segments if x)
            summary = (summary[:900] + "…") if len(summary) > 900 else summary
            if not summary:
                summary = "Summary unavailable for this lecture yet."

            lectures.append({
                "lecture_id": lecture_id,
                "key_topics": key_topics,
                "summary": summary,
            })
        except Exception as exc:
            logger.warning("Failed to build summary for '%s': %s", path.name, exc)

    return {"lectures": lectures}


def ingest_transcript_segments(
    transcript_segments: List[Dict[str, Any]],
    title: Optional[str] = None,
    lecture_id: Optional[str] = None,
    video_id: Optional[str] = None,
    source_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ingest pre-fetched transcript segments (e.g., from client-side YouTube API).

    Parameters
    ----------
    transcript_segments : List[Dict[str, Any]]
        List of transcript segments with keys:
        - text (str): segment text
        - start (float): start time in seconds
        - duration (float): segment duration in seconds
    title : str, optional
        Lecture title (used to generate lecture_id if not provided)
    lecture_id : str, optional
        Custom lecture ID. If not provided, generated from title or timestamp.
    video_id : str, optional
        YouTube video ID (stored in metadata)
    source_url : str, optional
        Full source URL (stored for playback links)

    Returns
    -------
    Dict with keys: lecture_id, num_segments, num_chunks, indexed_vectors, duration_s, message
    """
    # Resolve lecture_id
    if not lecture_id:
        if title:
            lecture_id = _slugify(title)
        else:
            lecture_id = f"lecture_{int(__import__('time').time())}"

    logger.info("ingest_transcript_segments: lecture_id='%s', segments=%d", lecture_id, len(transcript_segments))

    # Convert transcript segments to normalized format expected by _index_transcript_segments
    normalized_segments = []
    total_duration = 0.0

    for i, seg in enumerate(transcript_segments):
        text = seg.get("text", "").strip()
        if not text:
            continue

        start = float(seg.get("start", 0.0))
        duration = float(seg.get("duration", 0.0))
        end = start + duration

        normalized_segments.append({
            "id": i,
            "seek": start,
            "start": start,
            "end": end,
            "text": text,
        })
        total_duration = max(total_duration, end)

    if not normalized_segments:
        raise ValueError("No valid transcript segments provided.")

    # Index the segments
    result = _index_transcript_segments(
        segments=normalized_segments,
        lecture_id=lecture_id,
        source_url=source_url,
        audio_path=f"youtube_video_{video_id}" if video_id else "",
    )

    # Update source map if we have a video_id
    if video_id:
        source_map = _load_source_map()
        # Build YouTube URL
        yt_url = f"https://www.youtube.com/watch?v={video_id}"
        source_map[lecture_id] = yt_url
        _save_source_map(source_map)
        logger.info("Stored source URL for '%s': %s", lecture_id, yt_url)

    return result


def ingest_raw_text(
    text: str,
    title: Optional[str] = None,
    lecture_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ingest raw text (e.g., manually pasted transcript) directly into ChromaDB.

    Parameters
    ----------
    text : str
        Raw text to ingest (lecture notes, transcript, etc.)
    title : str, optional
        Lecture title (used to generate lecture_id if not provided)
    lecture_id : str, optional
        Custom lecture ID. If not provided, generated from title or timestamp.

    Returns
    -------
    Dict with keys: lecture_id, num_segments, num_chunks, indexed_vectors, duration_s, message
    """
    # Resolve lecture_id
    if not lecture_id:
        if title:
            lecture_id = _slugify(title)
        else:
            lecture_id = f"lecture_{int(__import__('time').time())}"

    logger.info("ingest_raw_text: lecture_id='%s', text_length=%d", lecture_id, len(text))

    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")

    # Create a pseudo-transcript from the raw text
    # Split by newlines and treat each non-empty line as a segment
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    if not lines:
        raise ValueError("No valid text content found after parsing.")

    # Create segments with dummy timestamps (no real timing info)
    segments = []
    for i, line in enumerate(lines):
        segments.append({
            "id": i,
            "seek": 0.0,
            "start": 0.0,
            "end": 0.0,
            "text": line,
        })

    # Index the segments
    result = _index_transcript_segments(
        segments=segments,
        lecture_id=lecture_id,
        source_url="",
        audio_path="",
    )

    # Note: duration will be 0 since we don't have real timing info
    return result
