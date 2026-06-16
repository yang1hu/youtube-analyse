import json
import os
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from creator_agent.agent.runtime import AgentRuntime
from creator_agent.config import Settings
from creator_agent.services.sample_analysis_service import SampleAnalysisService
from creator_agent.services.database_workspace_store import DatabaseWorkspaceStore
from creator_agent.services.settings_service import WorkspaceSettingsService
from creator_agent.services.transcript_store import TranscriptStore
from creator_agent.services.workspace_shapes import empty_workspace_data
from creator_agent.tools import build_default_registry
from creator_agent.tools.channel_history import get_channel_recent_videos


_WORKSPACE_LOCKS: dict[Path, threading.RLock] = {}
_WORKSPACE_LOCKS_GUARD = threading.Lock()


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def unique_workspace_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class WorkspaceStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.path = Path(self.settings.workspace_data_path)
        self._lock = self._lock_for(self.path)
        self._database_store: DatabaseWorkspaceStore | None = None

    def load(self) -> dict[str, Any]:
        if self._use_database():
            return self._db().load()
        with self._lock:
            if not self.path.exists():
                return empty_workspace_data()
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except JSONDecodeError as exc:
                backup_path = self._backup_corrupt_workspace_file()
                raise RuntimeError(f"Workspace data file is invalid JSON. A backup was saved to {backup_path}.") from exc
            return {**empty_workspace_data(), **data}

    def save(self, data: dict[str, Any]) -> dict[str, Any]:
        if self._use_database():
            return self._db().save(data)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            normalized = {**empty_workspace_data(), **data}
            self._atomic_write_json(normalized)
            return normalized

    def update(self, mutator: Callable[[dict[str, Any]], Any]) -> tuple[dict[str, Any], Any]:
        if self._use_database():
            data = self.load()
            result = mutator(data)
            return self.save(data), result
        with self._lock:
            if self.path.exists():
                try:
                    data = json.loads(self.path.read_text(encoding="utf-8"))
                except JSONDecodeError as exc:
                    backup_path = self._backup_corrupt_workspace_file()
                    raise RuntimeError(f"Workspace data file is invalid JSON. A backup was saved to {backup_path}.") from exc
            else:
                data = empty_workspace_data()
            normalized = {**empty_workspace_data(), **data}
            result = mutator(normalized)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_write_json(normalized)
            return normalized, result

    def _atomic_write_json(self, data: dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        temp_path = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        temp_path.write_text(payload, encoding="utf-8")
        temp_path.replace(self.path)

    def _backup_corrupt_workspace_file(self) -> Path:
        backup_path = self.path.with_name(f"{self.path.name}.corrupt-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}")
        self.path.replace(backup_path)
        return backup_path

    def _use_database(self) -> bool:
        if os.getenv("YCA_WORKSPACE_DATA_PATH"):
            return False
        return bool(self.settings.database_url)

    def _db(self) -> DatabaseWorkspaceStore:
        if self._database_store is None:
            self._database_store = DatabaseWorkspaceStore(self.settings)
        return self._database_store

    def _lock_for(self, path: Path) -> threading.RLock:
        resolved = path.resolve()
        with _WORKSPACE_LOCKS_GUARD:
            if resolved not in _WORKSPACE_LOCKS:
                _WORKSPACE_LOCKS[resolved] = threading.RLock()
            return _WORKSPACE_LOCKS[resolved]

    def dashboard(self) -> dict[str, Any]:
        data = self.load()
        workspace_settings = WorkspaceSettingsService(self.settings).get()
        channels = data["channels"]
        recent_videos = data["recent_videos"]
        configured_urls = self._configured_channel_urls(workspace_settings)
        if configured_urls:
            channel_by_url = {str(channel.get("url") or ""): channel for channel in channels}
            configured_channels = []
            for channel_url in configured_urls:
                configured_channel = channel_by_url.get(channel_url)
                channel_title = channel_url.rstrip("/").split("/")[-1]
                configured_channels.append(
                    {
                        "id": channel_url,
                        "title": configured_channel.get("title") if configured_channel else channel_title,
                        "url": channel_url,
                        "subscriber_count": configured_channel.get("subscriber_count", 0) if configured_channel else 0,
                        "video_count": configured_channel.get("video_count", 0) if configured_channel else 0,
                        "collection_status": configured_channel.get("collection_status", "configured") if configured_channel else "configured",
                        "collection_error": configured_channel.get("collection_error", "") if configured_channel else "",
                        "synced_at": configured_channel.get("synced_at", "") if configured_channel else "",
                    }
                )
            channels = configured_channels
            configured_titles = {str(channel.get("title") or "") for channel in configured_channels}
            recent_videos = [
                video
                for video in recent_videos
                if str(video.get("channel_url") or "") in configured_urls
                or str(video.get("channel_title") or "") in configured_titles
            ]
        return {
            "channels": channels,
            "recent_videos": recent_videos,
            "idea_cards": data["idea_cards"],
            "jobs": data["jobs"],
            "comment_collector_status": "not_configured",
        }

    def sync_channel(self) -> dict[str, Any]:
        workspace_settings = WorkspaceSettingsService(self.settings).get()
        channel_urls = self._configured_channel_urls(workspace_settings)
        if not channel_urls:
            raise ValueError("Channel URL is required before syncing.")

        data = self.load()
        synced_at = utc_now_iso()
        existing_videos = [
            video
            for video in data["recent_videos"]
            if str(video.get("channel_url") or "") not in channel_urls
        ]
        synced_channels: list[dict[str, Any]] = []
        synced_videos: list[dict[str, Any]] = []

        for channel_url in channel_urls:
            channel_title = channel_url.rstrip("/").split("/")[-1]
            try:
                collection = get_channel_recent_videos(channel_id=channel_title, channel_url=channel_url)
                videos = [
                    {
                        "id": item.get("youtube_video_id") or item.get("id") or item.get("url"),
                        "youtube_video_id": item.get("youtube_video_id") or item.get("id"),
                        "title": item.get("title") or "Untitled video",
                        "url": item.get("url") or "",
                        "channel_title": channel_title,
                        "channel_url": channel_url,
                        "published_text": item.get("published_text") or "",
                        "published_at": item.get("published_text") or "",
                        "view_count": item.get("view_count") or 0,
                        "analysis_status": self._video_analysis_status(data, item.get("url") or ""),
                    }
                    for item in collection.get("videos", [])
                ]
                collection_status = collection.get("collection_status", "ok")
                collection_error = collection.get("collection_error", "")
            except Exception as exc:
                videos = [
                    video
                    for video in data["recent_videos"]
                    if str(video.get("channel_url") or "") == channel_url
                    or str(video.get("channel_title") or "") == channel_title
                ]
                collection_status = "failed"
                collection_error = str(exc)

            channel = {
                "id": channel_url,
                "title": channel_title,
                "url": channel_url,
                "subscriber_count": 0,
                "video_count": len(videos),
                "collection_status": collection_status,
                "collection_error": collection_error,
                "synced_at": synced_at,
            }
            synced_channels.append(channel)
            synced_videos.extend(videos)

        existing_channels = [
            channel
            for channel in data["channels"]
            if str(channel.get("url") or "") not in channel_urls
        ]
        data["channels"] = synced_channels + existing_channels
        data["recent_videos"] = self._dedupe_videos(synced_videos + existing_videos)
        self.save(data)
        return {
            "channel": synced_channels[0] if synced_channels else None,
            "channels": synced_channels,
            "videos": synced_videos,
        }

    def analyze_video(self, video_url: str, progress_callback: Callable[[str], None] | None = None) -> dict[str, Any]:
        job = {
            "id": unique_workspace_id("job"),
            "kind": "video_analysis",
            "status": "running",
            "target_url": video_url,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        }

        def save_started(data: dict[str, Any]) -> None:
            data["jobs"].insert(0, job)

        self.update(save_started)

        try:
            result = AgentRuntime(build_default_registry()).run_video_analysis(video_url, progress_callback=progress_callback)
            metadata = result.tool_results.get("get_video_metadata", {})
            transcript = result.tool_results.get("get_transcript", {})
            video_id = str(metadata.get("youtube_video_id") or metadata.get("video_id") or "")
            if video_id and transcript.get("text"):
                TranscriptStore(self.settings).save_transcript(
                    video_id=video_id,
                    video_url=video_url,
                    title=str(metadata.get("title") or ""),
                    source=str(transcript.get("source") or ""),
                    language=str(transcript.get("language") or ""),
                    raw_text=str(transcript.get("text") or ""),
                )
            report_json = result.report.model_dump()
            report = {
                "id": unique_workspace_id("report"),
                "youtube_video_id": video_id,
                "video_url": video_url,
                "video_title": metadata.get("title") or report_json["creative_breakdown"]["title_hook"],
                "channel_title": (metadata.get("channel") or {}).get("title") or "",
                "summary": report_json["summary"],
                "creative_breakdown": report_json["creative_breakdown"],
                "growth_judgement": report_json["growth_judgement"],
                "idea_cards": report_json["idea_cards"],
                "comment_insights": report_json["comment_insights"],
                "collection_evidence": self._collection_evidence(result.tool_results),
                "created_at": utc_now_iso(),
            }
            if progress_callback:
                progress_callback("save_report")
            idea_cards = [
                {
                    "id": unique_workspace_id("idea"),
                    "source": report["video_title"],
                    "source_video_url": video_url,
                    **idea,
                }
                for idea in report_json["idea_cards"]
            ]

            job["status"] = "complete"
            job["current_step"] = "complete"
            job["report_id"] = report["id"]
            job["updated_at"] = utc_now_iso()

            def save_success(data: dict[str, Any]) -> None:
                for stored_job in data["jobs"]:
                    if str(stored_job.get("id") or "") == job["id"]:
                        stored_job.update(job)
                        break
                else:
                    data["jobs"].insert(0, job)
                data["reports"].insert(0, report)
                data["idea_cards"] = idea_cards + data["idea_cards"]
                self._mark_video_analyzed(data, video_url)

            self.update(save_success)
            return {"job": job, "report": report, "idea_cards": idea_cards}
        except Exception as exc:
            job["status"] = "failed"
            job["current_step"] = "failed"
            job["error_message"] = str(exc)
            job["updated_at"] = utc_now_iso()

            def save_failure(data: dict[str, Any]) -> None:
                for stored_job in data["jobs"]:
                    if str(stored_job.get("id") or "") == job["id"]:
                        stored_job.update(job)
                        return
                data["jobs"].insert(0, job)

            self.update(save_failure)
            return {"job": job, "error": str(exc)}

    def latest_report(self) -> dict[str, Any] | None:
        reports = self.reports()
        return reports[0] if reports else None

    def reports(self) -> list[dict[str, Any]]:
        data = self.load()
        return [self._enrich_report(report, data) for report in data["reports"]]

    def sample_analyses(self) -> list[dict[str, Any]]:
        return self.load()["sample_analyses"]

    def create_sample_analysis(self, video_url: str, video_title: str = "", video_id: str = "") -> dict[str, Any]:
        data = self.load()
        result = SampleAnalysisService(self.settings).analyze_video_opening(
            video_url=video_url,
            video_title=video_title,
            video_id=video_id,
        )
        data["sample_analyses"] = [
            sample for sample in data["sample_analyses"] if sample.get("id") != result.get("id")
        ]
        data["sample_analyses"].insert(0, result)
        self.save(data)
        return result

    def report_by_id(self, report_id: str) -> dict[str, Any] | None:
        data = self.load()
        for report in data["reports"]:
            if str(report.get("id") or "") == report_id:
                return self._enrich_report(report, data)
        return None

    def ideas(self) -> list[dict[str, Any]]:
        data = self.load()
        report_ideas = self._llm_report_ideas(data)
        if report_ideas:
            return report_ideas
        return data["idea_cards"]

    def prune_stale_ideas(self) -> dict[str, Any]:
        data = self.load()
        before_count = len(data["idea_cards"])
        data["idea_cards"] = self._llm_report_ideas(data)
        self.save(data)
        return {
            "before_count": before_count,
            "after_count": len(data["idea_cards"]),
            "removed_count": max(0, before_count - len(data["idea_cards"])),
            "idea_cards": data["idea_cards"],
        }

    def _llm_report_ideas(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        report_ideas: list[dict[str, Any]] = []
        for report in data["reports"]:
            evidence = report.get("collection_evidence") if isinstance(report.get("collection_evidence"), dict) else {}
            if evidence.get("analysis_source") != "llm" or evidence.get("analysis_status") != "ok":
                continue
            ideas = report.get("idea_cards") if isinstance(report.get("idea_cards"), list) else []
            for index, idea in enumerate(ideas):
                if not isinstance(idea, dict):
                    continue
                report_ideas.append(
                    {
                        "id": idea.get("id") or f"{report.get('id', 'report')}-idea-{index + 1}",
                        "source": report.get("video_title") or "Source video",
                        "source_video_url": report.get("video_url") or "",
                        "source_report_id": report.get("id") or "",
                        "analysis_source": evidence.get("analysis_source") or "",
                        "analysis_status": evidence.get("analysis_status") or "",
                        **idea,
                        "score": self._normalized_score(idea.get("score")),
                    }
                )
        return report_ideas

    def _normalized_score(self, value: Any) -> int:
        try:
            score = int(value)
        except (TypeError, ValueError):
            return 60
        if 0 < score <= 10:
            score *= 10
        return max(0, min(100, score))

    def _video_analysis_status(self, data: dict[str, Any], video_url: str) -> str:
        if any(report.get("video_url") == video_url for report in data["reports"]):
            return "complete"
        return "pending"

    def _mark_video_analyzed(self, data: dict[str, Any], video_url: str) -> None:
        for video in data["recent_videos"]:
            if video.get("url") == video_url:
                video["analysis_status"] = "complete"

    def _configured_channel_urls(self, workspace_settings: Any) -> list[str]:
        urls = list(getattr(workspace_settings, "channel_urls", []) or [])
        legacy_url = str(getattr(workspace_settings, "channel_url", "") or "")
        if legacy_url and legacy_url not in urls:
            urls.insert(0, legacy_url)
        return urls

    def _dedupe_videos(self, videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for video in videos:
            key = str(video.get("url") or video.get("youtube_video_id") or video.get("id") or "")
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            deduped.append(video)
        return deduped

    def _collection_evidence(self, tool_results: dict[str, dict]) -> dict[str, Any]:
        metadata = tool_results.get("get_video_metadata", {})
        transcript = tool_results.get("get_transcript", {})
        comments = tool_results.get("get_comments", {})
        llm_analysis = tool_results.get("analyze_with_llm", {})
        transcript_source = str(transcript.get("source") or "")
        transcript_text = str(transcript.get("text") or "")
        analysis_source = str(llm_analysis.get("source") or "")
        analysis_status = str(llm_analysis.get("status") or "")
        return {
            "metadata_source": metadata.get("collection_source") or "",
            "metadata_status": metadata.get("collection_status") or "",
            "transcript_source": transcript_source,
            "transcript_language": transcript.get("language") or "",
            "transcript_status": "ok" if transcript_text else "missing",
            "transcript_length": len(transcript_text),
            "is_auto_caption": self._is_auto_caption(transcript_source),
            "transcript_error": transcript.get("error_message") or "",
            "comments_status": comments.get("status") or "",
            "analysis_source": analysis_source,
            "analysis_status": analysis_status,
            "analysis_error": llm_analysis.get("error_message") or "",
            "llm_participated": analysis_source == "llm" and analysis_status == "ok",
            "used_rule_fallback": analysis_source == "rule_fallback" or analysis_status == "failed",
        }

    def _enrich_report(self, report: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        enriched = {**report}
        evidence = {
            **(report.get("collection_evidence") if isinstance(report.get("collection_evidence"), dict) else {})
        }
        video_id = str(report.get("youtube_video_id") or "")
        transcript_record = TranscriptStore(self.settings).get_transcript(video_id) if video_id else None
        transcript_source = str(transcript_record.get("transcript_source") if transcript_record else evidence.get("transcript_source") or "")
        transcript_length = (
            int(transcript_record.get("raw_length") or 0)
            if transcript_record
            else self._as_int(evidence.get("transcript_length"))
        )
        transcript_language = str(transcript_record.get("language") if transcript_record else evidence.get("transcript_language") or "")
        analysis_source = str(evidence.get("analysis_source") or "")
        analysis_status = str(evidence.get("analysis_status") or "")
        sample = self._sample_for_report(report, data)
        frame_count = self._as_int(sample.get("frame_count")) if sample else self._as_int(evidence.get("frame_count"))

        evidence.update(
            {
                "transcript_source": transcript_source,
                "transcript_language": transcript_language,
                "transcript_status": "ok" if transcript_length > 0 else evidence.get("transcript_status") or "missing",
                "transcript_length": transcript_length,
                "is_auto_caption": self._is_auto_caption(transcript_source),
                "llm_participated": analysis_source == "llm" and analysis_status == "ok",
                "used_rule_fallback": analysis_source == "rule_fallback" or analysis_status == "failed",
                "frame_status": "ok" if frame_count > 0 else "missing",
                "frame_count": frame_count,
            }
        )
        enriched["collection_evidence"] = evidence
        return enriched

    def _sample_for_report(self, report: dict[str, Any], data: dict[str, Any]) -> dict[str, Any] | None:
        video_url = str(report.get("video_url") or "")
        video_id = str(report.get("youtube_video_id") or "")
        for sample in data["sample_analyses"]:
            if not isinstance(sample, dict):
                continue
            if video_url and str(sample.get("video_url") or "") == video_url:
                return sample
            if video_id and str(sample.get("video_id") or "") == video_id:
                return sample
        return None

    def _is_auto_caption(self, source: str) -> bool:
        normalized = source.lower()
        return "auto" in normalized or "automatic" in normalized

    def _as_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
