from __future__ import annotations

import re
import sys
import subprocess
from pathlib import Path
from typing import Any

from config import settings

FILLER_PATTERN = re.compile(
    r"\b(um+|uh+|like|you know|sort of|kind of|actually|basically|literally)\b",
    re.IGNORECASE,
)


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

        # Prefer Python API to avoid PATH issues for yt-dlp binary.
        try:
            import yt_dlp

            ydl_opts = {
                "format": "mp4/best",
                "noplaylist": True,
                "outtmpl": out_tmpl,
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception:
            # Fallback: run module directly with the active Python executable.
            cmd = [
                sys.executable,
                "-m",
                "yt_dlp",
                "-f",
                "mp4/best",
                "--no-playlist",
                "-o",
                out_tmpl,
                url,
            ]
            subprocess.run(cmd, check=True)

        files = sorted(out_dir.glob("source.*"))
        if not files:
            raise RuntimeError("Failed to download YouTube video")
        return files[0]

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
