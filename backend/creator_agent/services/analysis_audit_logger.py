from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from creator_agent.config import Settings


class AnalysisAuditLogger:
    def __init__(self, settings: Settings | None = None, run_id: str | None = None) -> None:
        self.settings = settings or Settings()
        self.run_id = run_id or f"analysis-{uuid.uuid4().hex[:12]}"
        self.path = Path(self.settings.analysis_log_path)

    def write(self, event: str, **payload: Any) -> None:
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "run_id": self.run_id,
            "event": event,
            **self._sanitize(payload),
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, default=str) + os.linesep)
        except Exception:
            return

    def summarize_tool_request(self, name: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        return {"tool": name, "params": self._compact(kwargs)}

    def summarize_tool_result(self, name: str, result: dict[str, Any]) -> dict[str, Any]:
        summary: dict[str, Any] = {"tool": name}
        for key in [
            "status",
            "source",
            "collection_status",
            "collection_source",
            "language",
            "error_message",
            "youtube_video_id",
            "video_id",
            "title",
        ]:
            if key in result:
                summary[key] = self._compact(result[key])
        if "text" in result:
            summary["text_chars"] = len(str(result.get("text") or ""))
        if "description" in result:
            summary["description_chars"] = len(str(result.get("description") or ""))
        if "videos" in result and isinstance(result["videos"], list):
            summary["videos_count"] = len(result["videos"])
        if "comments" in result and isinstance(result["comments"], list):
            summary["comments_count"] = len(result["comments"])
        if len(summary) == 1:
            summary["keys"] = sorted(result.keys())
        return summary

    def summarize_llm_request(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        input_text = str(payload.get("input") or "")
        decoded_input: dict[str, Any] = {}
        try:
            parsed = json.loads(input_text)
            if isinstance(parsed, dict):
                decoded_input = parsed
        except json.JSONDecodeError:
            decoded_input = {}

        transcript = decoded_input.get("transcript") if isinstance(decoded_input.get("transcript"), dict) else {}
        metadata = decoded_input.get("video_metadata") if isinstance(decoded_input.get("video_metadata"), dict) else {}
        return {
            "url": url,
            "model": payload.get("model"),
            "instructions_chars": len(str(payload.get("instructions") or "")),
            "input_chars": len(input_text),
            "video_title": self._compact(metadata.get("title")),
            "video_id": metadata.get("youtube_video_id") or metadata.get("video_id"),
            "transcript_source": transcript.get("source"),
            "transcript_language": transcript.get("language"),
            "transcript_chars": len(str(transcript.get("text") or "")),
            "payload_keys": sorted(payload.keys()),
        }

    def summarize_llm_response(self, data: dict[str, Any], text: str) -> dict[str, Any]:
        return {
            "response_id": data.get("id"),
            "status": data.get("status"),
            "model": data.get("model"),
            "output_text_chars": len(text),
            "json_chars": len(json.dumps(data, ensure_ascii=False, default=str)),
        }

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            sanitized: dict[str, Any] = {}
            for key, item in value.items():
                lowered = str(key).lower()
                if "api_key" in lowered or lowered in {"authorization", "headers"}:
                    sanitized[key] = "[redacted]"
                else:
                    sanitized[key] = self._sanitize(item)
            return sanitized
        if isinstance(value, list):
            return [self._sanitize(item) for item in value[:50]]
        return self._compact(value)

    def _compact(self, value: Any) -> Any:
        if isinstance(value, str):
            if len(value) > 500:
                return f"{value[:500]}... [truncated {len(value) - 500} chars]"
            return value
        if isinstance(value, dict):
            return {str(key): self._compact(item) for key, item in list(value.items())[:50]}
        if isinstance(value, list):
            return [self._compact(item) for item in value[:20]]
        return value
