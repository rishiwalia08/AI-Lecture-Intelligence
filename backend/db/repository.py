from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from config import settings


class MetadataRepository:
    def __init__(self) -> None:
        self.base_dir = settings.data_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.meta_file = self.base_dir / "videos_metadata.json"
        if not self.meta_file.exists():
            self.meta_file.write_text("{}", encoding="utf-8")

    def _read_all(self) -> dict[str, Any]:
        return json.loads(self.meta_file.read_text(encoding="utf-8"))

    def _write_all(self, data: dict[str, Any]) -> None:
        self.meta_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def create_video(self, payload: dict[str, Any]) -> str:
        videos = self._read_all()
        video_id = payload.get("video_id") or str(uuid4())
        payload["video_id"] = video_id
        payload["created_at"] = datetime.now(timezone.utc).isoformat()
        videos[video_id] = payload
        self._write_all(videos)
        return video_id

    def update_video(self, video_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        videos = self._read_all()
        if video_id not in videos:
            raise KeyError(f"Video {video_id} not found")
        videos[video_id].update(updates)
        videos[video_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write_all(videos)
        return videos[video_id]

    def get_video(self, video_id: str) -> dict[str, Any] | None:
        return self._read_all().get(video_id)

    def list_videos(self) -> list[dict[str, Any]]:
        return list(self._read_all().values())


class ArtifactRepository:
    def __init__(self) -> None:
        self.artifacts_root = settings.data_dir / settings.artifacts_dir_name
        self.artifacts_root.mkdir(parents=True, exist_ok=True)

    def video_dir(self, video_id: str) -> Path:
        path = self.artifacts_root / video_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_json(self, video_id: str, filename: str, data: Any) -> Path:
        out = self.video_dir(video_id) / filename
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return out

    def load_json(self, video_id: str, filename: str) -> Any:
        path = self.video_dir(video_id) / filename
        if not path.exists():
            raise FileNotFoundError(path)
        return json.loads(path.read_text(encoding="utf-8"))
