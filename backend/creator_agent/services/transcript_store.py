import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from creator_agent.config import Settings


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class TranscriptStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.transcript_dir = Path(self.settings.transcript_cache_dir)
        self.translation_dir = Path(self.settings.translation_cache_dir)

    def save_transcript(
        self,
        *,
        video_id: str,
        video_url: str,
        title: str,
        source: str,
        language: str,
        raw_text: str,
    ) -> dict[str, Any]:
        record = {
            "video_id": video_id,
            "video_url": video_url,
            "title": title,
            "transcript_source": source,
            "language": language,
            "raw_text": raw_text,
            "raw_length": len(raw_text),
            "fetched_at": utc_now_iso(),
        }
        self.transcript_dir.mkdir(parents=True, exist_ok=True)
        self._transcript_path(video_id).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    def get_transcript(self, video_id: str) -> dict[str, Any] | None:
        path = self._transcript_path(video_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_translation(
        self,
        *,
        video_id: str,
        target_language: str,
        source_language: str,
        source_text_hash: str,
        translated_text: str,
        provider: str,
        model: str,
    ) -> dict[str, Any]:
        record = {
            "video_id": video_id,
            "target_language": target_language,
            "source_language": source_language,
            "source_text_hash": source_text_hash,
            "translated_text": translated_text,
            "translated_length": len(translated_text),
            "provider": provider,
            "model": model,
            "translated_at": utc_now_iso(),
        }
        self.translation_dir.mkdir(parents=True, exist_ok=True)
        self._translation_path(video_id, target_language).write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return record

    def save_translation_status(
        self,
        *,
        video_id: str,
        target_language: str,
        status: str,
        source_text_hash: str,
        translated_chunks: list[str],
        total_chunks: int,
        provider: str,
        model: str,
        error_message: str = "",
    ) -> dict[str, Any]:
        record = {
            "video_id": video_id,
            "target_language": target_language,
            "status": status,
            "source_text_hash": source_text_hash,
            "translated_chunks": translated_chunks,
            "translated_text": "\n\n".join(translated_chunks).strip(),
            "completed_chunks": len(translated_chunks),
            "total_chunks": total_chunks,
            "provider": provider,
            "model": model,
            "error_message": error_message,
            "updated_at": utc_now_iso(),
        }
        self.translation_dir.mkdir(parents=True, exist_ok=True)
        self._translation_status_path(video_id, target_language).write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return record

    def get_translation_status(self, video_id: str, target_language: str = "zh-CN") -> dict[str, Any] | None:
        path = self._translation_status_path(video_id, target_language)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def get_translation(self, video_id: str, target_language: str = "zh-CN") -> dict[str, Any] | None:
        path = self._translation_path(video_id, target_language)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _transcript_path(self, video_id: str) -> Path:
        return self.transcript_dir / f"{self._safe_video_id(video_id)}.json"

    def _translation_path(self, video_id: str, target_language: str) -> Path:
        safe_language = target_language.replace("/", "-")
        return self.translation_dir / f"{self._safe_video_id(video_id)}.{safe_language}.json"

    def _translation_status_path(self, video_id: str, target_language: str) -> Path:
        safe_language = target_language.replace("/", "-")
        return self.translation_dir / f"{self._safe_video_id(video_id)}.{safe_language}.status.json"

    def _safe_video_id(self, video_id: str) -> str:
        return "".join(char for char in video_id if char.isalnum() or char in {"-", "_"}) or "unknown-video"
