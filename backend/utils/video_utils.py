from __future__ import annotations

from urllib.parse import parse_qs, urlparse


def extract_youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "youtu.be" in host:
        return parsed.path.strip("/") or None

    if "youtube.com" in host:
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/")[-1].split("/")[0]
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/embed/")[-1].split("/")[0]

    return None


def youtube_timestamp_link(youtube_url: str | None, start_seconds: float) -> str | None:
    if not youtube_url:
        return None

    video_id = extract_youtube_video_id(youtube_url)
    if not video_id:
        return None

    return f"https://youtube.com/watch?v={video_id}&t={max(0, int(start_seconds))}"
