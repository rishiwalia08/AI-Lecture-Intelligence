from __future__ import annotations

import re
import sys
import subprocess
from pathlib import Path
from typing import Any
import json
from urllib.parse import parse_qs, urlparse

from config import settings

FILLER_PATTERN = re.compile(
    r"\b(um+|uh+|like|you know|sort of|kind of|actually|basically|literally)\b",
    re.IGNORECASE,
)


class YoutubeTranscriptUnavailableError(RuntimeError):
    pass


class VideoIngestionService:
    def __init__(self) -> None:
        self._whisper_model: Any | None = None

    @property
    def whisper_model(self) -> Any:
        if self._whisper_model is None:
            try:
                from faster_whisper import WhisperModel  # pyright: ignore[reportMissingImports]
            except ImportError as exc:
                raise RuntimeError(
                    "faster-whisper is not installed. Run: pip install -r backend/requirements.txt"
                ) from exc

            self._whisper_model = WhisperModel(
                settings.whisper_model_size,
                device="cpu",
                compute_type=settings.whisper_compute_type,
            )
        return self._whisper_model

    def download_youtube_video(self, url: str, out_dir: Path) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_tmpl = str(out_dir / "source.%(ext)s")
        normalized_url = self._normalize_youtube_url(url)

        # Try multiple profiles to handle Shorts/format quirks on hosted environments.
        profile_errors: list[str] = []

        ydl_profiles = [
            {
                "format": "best[ext=mp4]/best",
                "noplaylist": True,
                "outtmpl": out_tmpl,
                "quiet": True,
                "no_warnings": True,
            },
            {
                "format": "mp4/best",
                "noplaylist": True,
                "outtmpl": out_tmpl,
                "quiet": True,
                "no_warnings": True,
            },
            {
                "format": "bestaudio/best",
                "noplaylist": True,
                "outtmpl": out_tmpl,
                "quiet": True,
                "no_warnings": True,
            },
        ]

        # Prefer Python API to avoid PATH issues for yt-dlp binary.
        try:
            import yt_dlp

            for idx, ydl_opts in enumerate(ydl_profiles):
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([normalized_url])
                    break
                except Exception as exc:
                    profile_errors.append(f"profile_{idx + 1}_python_api: {exc}")
            else:
                raise RuntimeError(" | ".join(profile_errors))
        except Exception as exc:
            # Fallback: run module directly with the active Python executable.
            last_stderr = ""
            cli_formats = ["best[ext=mp4]/best", "mp4/best", "bestaudio/best"]
            for fmt in cli_formats:
                cmd = [
                    sys.executable,
                    "-m",
                    "yt_dlp",
                    "-f",
                    fmt,
                    "--no-playlist",
                    "-o",
                    out_tmpl,
                    normalized_url,
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode == 0:
                    last_stderr = ""
                    break
                last_stderr = (proc.stderr or proc.stdout or "").strip()
            if last_stderr:
                raise RuntimeError(
                    "yt-dlp failed for this URL. "
                    f"Original URL: {url} | Normalized URL: {normalized_url} | "
                    f"Error: {last_stderr[:500]}"
                ) from exc
            raise

        files = sorted(out_dir.glob("source.*"))
        if not files:
            raise RuntimeError("Failed to download YouTube video")
        return files[0]

    def _normalize_youtube_url(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            host = (parsed.netloc or "").lower()
            path = parsed.path or ""

            # Convert shorts URL to watch URL for more stable extraction.
            if "youtube.com" in host and path.startswith("/shorts/"):
                video_id = path.split("/shorts/")[-1].split("/")[0].split("?")[0]
                if video_id:
                    return f"https://www.youtube.com/watch?v={video_id}"

            # Convert youtu.be short link to watch URL.
            if "youtu.be" in host:
                video_id = path.strip("/").split("/")[0]
                if video_id:
                    return f"https://www.youtube.com/watch?v={video_id}"

            # Preserve normal watch URL if present.
            if "youtube.com" in host:
                query = parse_qs(parsed.query)
                video_id = (query.get("v") or [""])[0]
                if video_id:
                    return f"https://www.youtube.com/watch?v={video_id}"
        except Exception:
            pass
        return url

    def extract_youtube_video_id(self, url: str) -> str | None:
        normalized = self._normalize_youtube_url(url)
        try:
            parsed = urlparse(normalized)
            query = parse_qs(parsed.query)
            video_id = (query.get("v") or [""])[0]
            return video_id or None
        except Exception:
            return None

    def fetch_youtube_transcript(self, url: str) -> list[dict[str, Any]]:
        video_id = self.extract_youtube_video_id(url)
        if not video_id:
            raise RuntimeError("Could not parse YouTube video id for transcript fallback")

        try:
            from youtube_transcript_api import YouTubeTranscriptApi  # pyright: ignore[reportMissingImports]
        except Exception as exc:
            raise RuntimeError(
                "youtube-transcript-api is not installed. Add it to backend/requirements.txt"
            ) from exc

        def _normalize_transcript_payload(payload: Any) -> list[dict[str, Any]]:
            if payload is None:
                return []
            if hasattr(payload, "to_raw_data"):
                try:
                    payload = payload.to_raw_data()
                except Exception:
                    pass
            if isinstance(payload, dict):
                if isinstance(payload.get("transcript"), list):
                    payload = payload.get("transcript")
                elif isinstance(payload.get("snippets"), list):
                    payload = payload.get("snippets")
            if isinstance(payload, list):
                return [row for row in payload if isinstance(row, dict)]
            return []

        transcript_entries: list[dict[str, Any]] = []

        # Primary path: direct transcript fetch using the installed library.
        try:
            api_instance = YouTubeTranscriptApi()
            for languages in (["en"], ["en-US"], ["en-GB"], []):
                try:
                    if languages:
                        result = api_instance.fetch(video_id, languages=languages)
                    else:
                        result = api_instance.fetch(video_id)
                    transcript_entries = _normalize_transcript_payload(result)
                    if transcript_entries:
                        break
                except Exception:
                    continue
        except Exception:
            transcript_entries = []

        if not transcript_entries:
            raise YoutubeTranscriptUnavailableError(
                "This YouTube video transcript is blocked or unavailable. "
                "Try a normal watch URL with captions enabled, or upload the video file directly."
            )

        segments: list[dict[str, Any]] = []
        for row in transcript_entries:
            if isinstance(row, dict):
                start = float(row.get("start", 0.0))
                duration = float(row.get("duration", 0.0))
                text = (row.get("text") or "").strip()
            else:
                start = float(getattr(row, "start", 0.0))
                duration = float(getattr(row, "duration", 0.0))
                text = str(getattr(row, "text", "") or "").strip()
            if not text:
                continue
            segments.append({
                "start": start,
                "end": start + max(0.1, duration),
                "text": text,
            })

        if not segments:
            raise YoutubeTranscriptUnavailableError(
                "This YouTube video returned no usable transcript segments. Please upload the video file directly."
            )

        return segments

    def extract_audio(self, video_path: Path, out_dir: Path) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_path = out_dir / "audio.wav"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(audio_path),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return audio_path

    def transcribe_audio(self, audio_path: Path) -> list[dict[str, Any]]:
        segments, _ = self.whisper_model.transcribe(str(audio_path), vad_filter=True)
        return [
            {
                "start": float(seg.start),
                "end": float(seg.end),
                "text": seg.text.strip(),
            }
            for seg in segments
            if seg.text and seg.text.strip()
        ]

    def clean_text(self, text: str) -> str:
        text = FILLER_PATTERN.sub("", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def chunk_transcript(self, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not segments:
            return []

        chunks: list[dict[str, Any]] = []
        buffer_text: list[str] = []
        start_time = segments[0]["start"]
        prev_end = start_time

        for seg in segments:
            cleaned = self.clean_text(seg["text"])
            if not cleaned:
                continue

            pause = seg["start"] - prev_end
            current_text = " ".join(buffer_text)

            should_split = (
                len(current_text) > settings.chunk_max_chars
                or pause >= settings.chunk_pause_threshold_sec
            )

            if buffer_text and should_split:
                chunks.append(
                    {
                        "text": current_text.strip(),
                        "start_time": start_time,
                        "end_time": prev_end,
                    }
                )
                buffer_text = []
                start_time = seg["start"]

            buffer_text.append(cleaned)
            prev_end = seg["end"]

        if buffer_text:
            chunks.append(
                {
                    "text": " ".join(buffer_text).strip(),
                    "start_time": start_time,
                    "end_time": prev_end,
                }
            )

        for i, chunk in enumerate(chunks):
            chunk["chunk_id"] = f"chunk_{i}"

        return chunks
