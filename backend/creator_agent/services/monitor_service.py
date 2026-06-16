from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from creator_agent.config import Settings
from creator_agent.services.redis_task_queue import RedisTaskQueue
from creator_agent.services.settings_service import WorkspaceSettingsService
from creator_agent.services.task_service import TaskService
from creator_agent.services.workspace_store import WorkspaceStore


class MonitorService:
    def __init__(
        self,
        settings: Settings | None = None,
        store: WorkspaceStore | None = None,
        task_service: TaskService | None = None,
    ) -> None:
        self.settings = settings or Settings()
        self.store = store or WorkspaceStore(self.settings)
        self.task_service = task_service or TaskService(self.settings, self.store)
        self.queue = RedisTaskQueue(self.settings)

    def status(self) -> dict[str, Any]:
        workspace_settings = WorkspaceSettingsService(self.settings).get()
        channel_count = len(workspace_settings.channel_urls) if workspace_settings.channel_urls else (1 if workspace_settings.channel_url else 0)
        last_run_at = self.queue.get_monitor_last_run()
        return {
            "enabled": workspace_settings.monitor_enabled,
            "auto_analyze": workspace_settings.monitor_auto_analyze,
            "auto_translate": workspace_settings.monitor_auto_translate,
            "channel_count": channel_count,
            "interval_minutes": workspace_settings.monitor_interval_minutes,
            "min_views": workspace_settings.monitor_min_views,
            "last_run_at": last_run_at,
            "next_run_at": self._next_run_at(last_run_at, workspace_settings.monitor_interval_minutes),
            "redis": self.queue.status(),
        }

    def run_once(self, *, force: bool = False) -> dict[str, Any]:
        workspace_settings = WorkspaceSettingsService(self.settings).get()
        if not workspace_settings.monitor_enabled and not force:
            return {
                "status": "skipped",
                "reason": "Auto monitor is disabled.",
                "new_video_count": 0,
                "queued_analysis_count": 0,
                "skipped_analysis_count": 0,
            }

        before_urls = {str(video.get("url") or "") for video in self.store.load()["recent_videos"]}
        sync_result = self.store.sync_channel()
        videos = sync_result.get("videos", []) if isinstance(sync_result, dict) else []
        new_videos = [video for video in videos if str(video.get("url") or "") and str(video.get("url") or "") not in before_urls]

        queued = []
        skipped = []
        if workspace_settings.monitor_auto_analyze:
            for video in new_videos:
                if self._view_count(video) >= workspace_settings.monitor_min_views:
                    task_result = self.task_service.create_task(
                        "video_analysis",
                        {
                            "video_url": str(video.get("url") or ""),
                            "auto_translate": workspace_settings.monitor_auto_translate,
                            "target_language": "zh-CN",
                        },
                    )
                    queued.append(task_result["task"])
                else:
                    skipped.append(
                        {
                            "video_url": str(video.get("url") or ""),
                            "reason": "Below minimum view threshold.",
                            "view_count": self._view_count(video),
                        }
                    )

        finished_at = datetime.now(UTC).isoformat()
        self.queue.set_monitor_last_run(finished_at)
        return {
            "status": "complete",
            "channel": sync_result.get("channel") if isinstance(sync_result, dict) else None,
            "channels": sync_result.get("channels", []) if isinstance(sync_result, dict) else [],
            "new_video_count": len(new_videos),
            "queued_analysis_count": len(queued),
            "skipped_analysis_count": len(skipped),
            "new_videos": new_videos,
            "queued_tasks": queued,
            "skipped_videos": skipped,
            "ran_at": finished_at,
            "next_run_at": self._next_run_at(finished_at, workspace_settings.monitor_interval_minutes),
        }

    def run_if_due(self) -> dict[str, Any]:
        workspace_settings = WorkspaceSettingsService(self.settings).get()
        if not workspace_settings.monitor_enabled:
            return {"status": "skipped", "reason": "Auto monitor is disabled."}

        last_run_at = self.queue.get_monitor_last_run()
        if last_run_at and not self._is_due(last_run_at, workspace_settings.monitor_interval_minutes):
            return {
                "status": "skipped",
                "reason": "Auto monitor is not due yet.",
                "last_run_at": last_run_at,
                "next_run_at": self._next_run_at(last_run_at, workspace_settings.monitor_interval_minutes),
            }
        return self.run_once()

    def _view_count(self, video: dict[str, Any]) -> int:
        try:
            return int(video.get("view_count") or 0)
        except (TypeError, ValueError):
            return 0

    def _is_due(self, last_run_at: str, interval_minutes: int) -> bool:
        try:
            last_run = datetime.fromisoformat(last_run_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        return datetime.now(UTC) >= last_run + timedelta(minutes=interval_minutes)

    def _next_run_at(self, last_run_at: str, interval_minutes: int) -> str:
        if not last_run_at:
            return ""
        try:
            last_run = datetime.fromisoformat(last_run_at.replace("Z", "+00:00"))
        except ValueError:
            return ""
        return (last_run + timedelta(minutes=interval_minutes)).isoformat()
