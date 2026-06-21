from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from creator_agent.config import Settings
from creator_agent.services.analysis_audit_logger import AnalysisAuditLogger
from creator_agent.services.redis_task_queue import RedisTaskQueue
from creator_agent.services.workspace_store import WorkspaceStore, unique_workspace_id


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


TASK_STEPS: dict[str, list[tuple[str, str]]] = {
    "channel_sync": [
        ("queued", "Queued"),
        ("collect_channel", "Collecting channel videos"),
        ("save_videos", "Saving videos"),
        ("complete", "Complete"),
    ],
    "video_analysis": [
        ("queued", "Queued"),
        ("metadata", "Fetching metadata"),
        ("transcript", "Fetching transcript"),
        ("comments", "Collecting comments"),
        ("llm_analysis", "Running LLM analysis"),
        ("save_report", "Saving report"),
        ("complete", "Complete"),
    ],
    "translation": [
        ("queued", "Queued"),
        ("load_transcript", "Loading transcript"),
        ("llm_translation", "Translating with LLM"),
        ("save_translation", "Saving translation"),
        ("complete", "Complete"),
    ],
    "sample_analysis": [
        ("queued", "Queued"),
        ("load_script", "Loading first five minutes"),
        ("analyze_opening_script", "Analyzing opening script"),
        ("complete", "Complete"),
    ],
}


class TaskService:
    def __init__(self, settings: Settings | None = None, store: WorkspaceStore | None = None) -> None:
        self.settings = settings or Settings()
        self.store = store or WorkspaceStore(self.settings)
        self.queue = RedisTaskQueue(self.settings)

    def list_tasks(self) -> dict[str, Any]:
        data = self.store.load()
        return {
            "tasks": [self._normalize_task(job) for job in data["jobs"]],
            "redis": self.redis_status(),
            "queue": self.queue_status(),
        }

    def create_task(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = utc_now_iso()

        def add_task(data: dict[str, Any]) -> dict[str, Any]:
            task = {
                "id": self._next_task_id(data["jobs"]),
                "kind": kind,
                "status": "queued",
                "current_step": "queued",
                "target_url": payload.get("video_url") or payload.get("target_url") or "",
                "payload": payload,
                "created_at": now,
                "updated_at": now,
            }
            data["jobs"].insert(0, task)
            return task

        _data, task = self.store.update(add_task)
        enqueued = self.queue.enqueue(task["id"])
        if not enqueued:
            task = self._update_task(
                task["id"],
                queue_status="not_enqueued",
                queue_message="Redis queue is not reachable; run this task manually from Task Center.",
            )
        self._push_redis_event({"event": "queued", "task_id": task["id"], "kind": kind, "payload": payload})
        AnalysisAuditLogger(self.settings).write(
            "task_queued",
            task_id=task["id"],
            kind=kind,
            payload=payload,
            enqueued=enqueued,
            queue_status=task.get("queue_status", "enqueued" if enqueued else "not_enqueued"),
        )
        return {"task": self._normalize_task(task), "redis": self.redis_status(), "queue": self.queue_status(), "enqueued": enqueued}

    def create_batch_video_analysis_tasks(
        self,
        limit: int = 10,
        *,
        prioritize_candidates: bool = False,
        video_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        selected_urls = [url.strip() for url in (video_urls or []) if url.strip()]
        if limit < 1 and not selected_urls:
            raise ValueError("Limit must be at least 1.")
        data = self.store.load()
        existing_targets = {
            str(job.get("target_url") or job.get("payload", {}).get("video_url") or "")
            for job in data["jobs"]
            if str(job.get("kind") or "") == "video_analysis" and str(job.get("status") or "") in {"queued", "running"}
        }
        analyzed_targets = {str(report.get("video_url") or "") for report in data["reports"]}
        candidates: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []

        source_videos = data["recent_videos"]
        candidate_context: dict[str, dict[str, Any]] = {}
        if selected_urls:
            selected_set = set(selected_urls)
            by_url = {str(video.get("url") or ""): video for video in data["recent_videos"]}
            source_videos = [by_url[url] for url in selected_urls if url in by_url]
            missing = [url for url in selected_urls if url not in by_url]
            skipped.extend({"title": url, "reason": "not_found"} for url in missing)
            limit = len(selected_set)
        elif prioritize_candidates:
            topic_candidates = self._topic_candidates(data["recent_videos"], limit=len(data["recent_videos"]))
            candidate_urls = [candidate["url"] for candidate in topic_candidates]
            candidate_context = {str(candidate.get("url") or ""): candidate for candidate in topic_candidates}
            by_url = {str(video.get("url") or ""): video for video in data["recent_videos"]}
            ranked = [by_url[url] for url in candidate_urls if url in by_url]
            ranked_urls = {str(video.get("url") or "") for video in ranked}
            source_videos = ranked + [video for video in data["recent_videos"] if str(video.get("url") or "") not in ranked_urls]

        for video in source_videos:
            video_url = str(video.get("url") or "")
            if not video_url:
                skipped.append({"title": str(video.get("title") or ""), "reason": "missing_url"})
                continue
            if video_url in analyzed_targets or str(video.get("analysis_status") or "") == "complete":
                skipped.append({"title": str(video.get("title") or video_url), "reason": "already_analyzed"})
                continue
            if video_url in existing_targets:
                skipped.append({"title": str(video.get("title") or video_url), "reason": "already_queued"})
                continue
            candidates.append(video)
            if len(candidates) >= limit:
                break

        tasks = [
            self.create_task(
                "video_analysis",
                {
                    "video_url": str(video.get("url") or ""),
                    "video_title": str(video.get("title") or ""),
                    "video_id": str(video.get("youtube_video_id") or video.get("id") or ""),
                    "channel_title": str(video.get("channel_title") or ""),
                    "candidate_score": candidate_context.get(str(video.get("url") or ""), {}).get("score"),
                    "candidate_reasons": candidate_context.get(str(video.get("url") or ""), {}).get("reasons", []),
                    "candidate_topic_group": candidate_context.get(str(video.get("url") or ""), {}).get("topic_group", ""),
                    "candidate_freshness_bucket": candidate_context.get(str(video.get("url") or ""), {}).get("freshness_bucket", ""),
                    "candidate_view_bucket": candidate_context.get(str(video.get("url") or ""), {}).get("view_bucket", ""),
                    "candidate_viral_potential": candidate_context.get(str(video.get("url") or ""), {}).get("viral_potential"),
                    "candidate_story_fit": candidate_context.get(str(video.get("url") or ""), {}).get("story_fit"),
                    "candidate_structure_reuse_value": candidate_context.get(str(video.get("url") or ""), {}).get("structure_reuse_value"),
                    "candidate_risk_flags": candidate_context.get(str(video.get("url") or ""), {}).get("risk_flags", []),
                },
            )["task"]
            for video in candidates
        ]
        return {
            "tasks": tasks,
            "queued_count": len(tasks),
            "skipped_count": len(skipped),
            "skipped": skipped,
            "prioritized": prioritize_candidates,
            "selected": bool(selected_urls),
            "redis": self.redis_status(),
            "queue": self.queue_status(),
        }

    def _topic_candidates(self, recent_videos: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        candidates = []
        for video in recent_videos:
            video_url = str(video.get("url") or "")
            if not video_url:
                continue
            if str(video.get("analysis_status") or "pending") == "complete":
                continue
            score, reasons = self._topic_candidate_score(video)
            views = self._as_int(video.get("view_count"))
            published = str(video.get("published_at") or video.get("published_text") or "")
            dimensions = self._topic_candidate_dimensions(video, views, published)
            candidates.append(
                {
                    "url": video_url,
                    "score": score,
                    "reasons": reasons,
                    "view_count": views,
                    "title": str(video.get("title") or ""),
                    "topic_group": self._topic_group(video),
                    "freshness_bucket": self._freshness_bucket(published),
                    "view_bucket": self._view_bucket(views),
                    **dimensions,
                }
            )
        return sorted(candidates, key=lambda item: (-item["score"], -item["view_count"], item["title"]))[:limit]

    def _topic_candidate_score(self, video: dict[str, Any]) -> tuple[int, list[str]]:
        title = str(video.get("title") or "")
        published = str(video.get("published_at") or video.get("published_text") or "")
        views = self._as_int(video.get("view_count"))
        score = 30
        reasons: list[str] = []
        if views >= 100000:
            score += 35
            reasons.append("High view count")
        elif views >= 10000:
            score += 22
            reasons.append("Above-average view count")
        elif views >= 1000:
            score += 10
            reasons.append("Early traction")
        story_keywords = ["story", "recap", "revenge", "twist", "system", "secret", "反转", "故事", "系统", "打脸", "复仇", "隐藏", "逆袭"]
        matched = [keyword for keyword in story_keywords if keyword.lower() in title.lower()]
        if matched:
            score += min(24, 8 * len(matched))
            reasons.append("Story keywords: " + ", ".join(matched[:3]))
        if any(token in published.lower() for token in ["hour", "today", "minute", "刚刚", "小时", "今天"]):
            score += 12
            reasons.append("Fresh upload")
        return min(score, 100), reasons or ["Pending analysis"]

    def _topic_candidate_dimensions(self, video: dict[str, Any], views: int, published: str) -> dict[str, Any]:
        title = str(video.get("title") or "")
        topic_group = self._topic_group(video)
        viral_potential = 30
        if views >= 100000:
            viral_potential = 92
        elif views >= 10000:
            viral_potential = 78
        elif views >= 1000:
            viral_potential = 58
        if self._freshness_bucket(published) == "fresh":
            viral_potential = min(100, viral_potential + 12)
        story_fit = 42
        if topic_group != "general":
            story_fit += 28
        story_terms = ["story", "recap", "revenge", "twist", "system", "secret", "反转", "故事", "系统", "打脸", "复仇", "隐藏", "逆袭"]
        matched_story_terms = [term for term in story_terms if term.lower() in title.lower()]
        story_fit = min(100, story_fit + min(24, len(matched_story_terms) * 8))
        structure_reuse_value = min(100, 36 + (22 if topic_group in {"revenge", "system", "secret", "twist"} else 0) + (18 if views >= 10000 else 0) + (12 if self._freshness_bucket(published) != "older" else 0))
        risk_flags: list[str] = []
        if topic_group == "general":
            risk_flags.append("题材信号弱，可能不适合短片小说结构拆解。")
        if views < 1000:
            risk_flags.append("播放表现偏低，建议降低优先级。")
        if any(token in title.lower() for token in ["full movie", "episode", "official", "clip", "完整版", "第", "集"]):
            risk_flags.append("可能是长剧/片段内容，拆解前确认版权和完整语境。")
        if any(token in title.lower() for token in ["celebrity", "real story", "真实", "明星"]):
            risk_flags.append("可能涉及真人或真实事件，转化时避免复用身份和具体经历。")
        return {
            "viral_potential": viral_potential,
            "story_fit": story_fit,
            "structure_reuse_value": structure_reuse_value,
            "risk_flags": risk_flags or ["暂无明显候选风险。"],
        }

    def _topic_group(self, video: dict[str, Any]) -> str:
        title = str(video.get("title") or "").lower()
        if any(token in title for token in ["revenge", "复仇", "打脸", "逆袭"]):
            return "revenge"
        if any(token in title for token in ["system", "系统", "reward", "奖励"]):
            return "system"
        if any(token in title for token in ["secret", "hidden", "隐藏", "秘密"]):
            return "secret"
        if any(token in title for token in ["twist", "反转"]):
            return "twist"
        if any(token in title for token in ["story", "recap", "故事"]):
            return "story"
        return "general"

    def _freshness_bucket(self, published: str) -> str:
        normalized = published.lower()
        if any(token in normalized for token in ["minute", "hour", "today", "刚刚", "分钟", "小时", "今天"]):
            return "fresh"
        if any(token in normalized for token in ["day", "yesterday", "天", "昨天"]):
            return "recent"
        return "older"

    def _view_bucket(self, views: int) -> str:
        if views >= 100000:
            return "viral"
        if views >= 10000:
            return "rising"
        if views >= 1000:
            return "early"
        return "low"

    def retry_task(self, task_id: str) -> dict[str, Any]:
        now = utc_now_iso()

        def add_retry(data: dict[str, Any]) -> dict[str, Any]:
            source = next((job for job in data["jobs"] if str(job.get("id") or "") == task_id), None)
            if source is None:
                raise ValueError("Task not found.")
            if source.get("status") not in {"failed", "cancelled"}:
                raise ValueError("Only failed tasks can be retried.")
            retry = {
                **{
                    key: value
                    for key, value in source.items()
                    if key not in {"error_message", "report_id", "queue_status", "queue_message"}
                },
                "id": self._next_task_id(data["jobs"]),
                "status": "queued",
                "current_step": "queued",
                "retry_of": task_id,
                "created_at": now,
                "updated_at": now,
            }
            data["jobs"].insert(0, retry)
            return retry

        _data, retry = self.store.update(add_retry)
        enqueued = self.queue.enqueue(retry["id"])
        if not enqueued:
            retry = self._update_task(
                retry["id"],
                queue_status="not_enqueued",
                queue_message="Redis queue is not reachable; run this task manually from Task Center.",
            )
        self._push_redis_event({"event": "retry", "task_id": retry["id"], "kind": retry.get("kind")})
        return {"task": self._normalize_task(retry), "redis": self.redis_status(), "queue": self.queue_status(), "enqueued": enqueued}

    def run_task(self, task_id: str, *, from_queue: bool = False) -> dict[str, Any]:
        task, claimed = self._claim_queued_task(task_id)
        if not claimed:
            return {"task": self._normalize_task(task), "skipped": True, "reason": "Task is not queued."}
        if not from_queue:
            self.queue.remove(task_id)
        kind = str(task.get("kind") or "")
        payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}

        try:
            if kind == "channel_sync":
                self._update_task(task_id, status="running", current_step="collect_channel")
                result = self.store.sync_channel()
                return self._finish_task(task_id, result)
            if kind == "video_analysis":
                video_url = str(payload.get("video_url") or task.get("target_url") or "")
                if not video_url:
                    raise ValueError("Video URL is required.")
                before_ids = self._job_ids()
                self._update_task(task_id, status="running", current_step="metadata")
                result = self.store.analyze_video(
                    video_url,
                    progress_callback=lambda step: self._update_task(task_id, status="running", current_step=step),
                )
                self._remove_new_jobs(before_ids, keep_task_id=task_id)
                if result.get("job", {}).get("status") == "failed":
                    raise RuntimeError(str(result.get("error") or result.get("job", {}).get("error_message") or "Video analysis failed."))
                if payload.get("auto_translate"):
                    translation_task = self._queue_translation_for_report(result.get("report"), payload)
                    if translation_task:
                        result["auto_translation_task"] = translation_task
                return self._finish_task(task_id, result, report_id=result.get("report", {}).get("id"))
            if kind == "sample_analysis":
                self._update_task(task_id, status="running", current_step="load_script")
                self._update_task(task_id, status="running", current_step="analyze_opening_script")
                result = self.store.create_sample_analysis(
                    video_url=str(payload.get("video_url") or ""),
                    video_title=str(payload.get("video_title") or ""),
                    video_id=str(payload.get("video_id") or ""),
                )
                return self._finish_task(task_id, {"sample_analysis": result})
            if kind == "translation":
                from creator_agent.services.translation_service import TranslationService

                self._update_task(task_id, status="running", current_step="load_transcript")
                self._update_task(task_id, status="running", current_step="llm_translation")
                result = TranslationService(self.settings).get_or_translate(
                    str(payload.get("video_id") or ""),
                    target_language=str(payload.get("target_language") or "zh-CN"),
                    force=bool(payload.get("force", False)),
                )
                self._update_task(task_id, status="running", current_step="save_translation")
                return self._finish_task(task_id, {"status": "complete", "translation": result})
        except Exception as exc:
            return self._fail_task(task_id, exc)

        return self._fail_task(task_id, ValueError(f"Unsupported task kind: {kind}"))

    def redis_status(self) -> dict[str, Any]:
        return self.queue.status()

    def queue_status(self) -> dict[str, Any]:
        return self.queue.status()

    def run_next_queued_task(self) -> dict[str, Any]:
        task_id = self.queue.dequeue(timeout_seconds=0)
        while task_id:
            try:
                task = self._task_by_id(task_id)
            except ValueError:
                self._push_redis_event({"event": "stale_queue_item", "task_id": task_id})
                task_id = self.queue.dequeue(timeout_seconds=0)
                continue
            if str(task.get("status") or "") == "queued":
                return self.run_task(task_id, from_queue=True)
            task_id = self.queue.dequeue(timeout_seconds=0)
        return {"task": None, "queue": self.queue_status(), "message": "No queued task is available in Redis."}

    def _push_redis_event(self, payload: dict[str, Any]) -> None:
        self.queue.push_event(payload)

    def _normalize_task(self, job: dict[str, Any]) -> dict[str, Any]:
        kind = str(job.get("kind") or job.get("type") or "video_analysis")
        current_step = str(job.get("current_step") or job.get("status") or "queued")
        steps = self._steps_for(kind, current_step, str(job.get("status") or "queued"))
        return {
            **job,
            "kind": kind,
            "current_step": current_step,
            "current_step_label": self._step_label(kind, current_step),
            "steps": steps,
        }

    def _task_by_id(self, task_id: str) -> dict[str, Any]:
        data = self.store.load()
        task = next((job for job in data["jobs"] if str(job.get("id") or "") == task_id), None)
        if task is None:
            raise ValueError("Task not found.")
        return task

    def _claim_queued_task(self, task_id: str) -> tuple[dict[str, Any], bool]:
        def claim(data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
            for job in data["jobs"]:
                if str(job.get("id") or "") != task_id:
                    continue
                if str(job.get("status") or "") != "queued":
                    return job, False
                job["status"] = "running"
                job["current_step"] = job.get("current_step") if job.get("current_step") != "queued" else "queued"
                job["started_at"] = job.get("started_at") or utc_now_iso()
                job["updated_at"] = utc_now_iso()
                return job, True
            raise ValueError("Task not found.")

        _data, result = self.store.update(claim)
        if result[1]:
            self._push_redis_event({"event": "claimed", "task_id": task_id, "status": "running"})
            AnalysisAuditLogger(self.settings).write(
                "task_claimed",
                task_id=task_id,
                kind=result[0].get("kind") or result[0].get("type"),
                payload=result[0].get("payload") if isinstance(result[0].get("payload"), dict) else {},
            )
        return result

    def _update_task(self, task_id: str, **updates: Any) -> dict[str, Any]:
        def update(data: dict[str, Any]) -> dict[str, Any]:
            for job in data["jobs"]:
                if str(job.get("id") or "") == task_id:
                    job.update(updates)
                    job["updated_at"] = utc_now_iso()
                    return job
            raise ValueError("Task not found.")

        _data, job = self.store.update(update)
        self._push_redis_event({"event": "updated", "task_id": task_id, **updates})
        return job

    def _finish_task(self, task_id: str, result: dict[str, Any], report_id: str | None = None) -> dict[str, Any]:
        updates: dict[str, Any] = {
            "status": "complete",
            "current_step": "complete",
            "result_json": result,
        }
        if report_id:
            updates["report_id"] = report_id
        task = self._update_task(task_id, **updates)
        AnalysisAuditLogger(self.settings).write(
            "task_finished",
            task_id=task_id,
            kind=task.get("kind") or task.get("type"),
            status="complete",
            report_id=report_id,
            result=self._result_summary(result),
        )
        return {"task": self._normalize_task(task), "result": result}

    def _fail_task(self, task_id: str, exc: Exception) -> dict[str, Any]:
        task = self._update_task(
            task_id,
            status="failed",
            current_step="failed",
            error_message=self._human_error_message(exc),
        )
        AnalysisAuditLogger(self.settings).write(
            "task_finished",
            task_id=task_id,
            kind=task.get("kind") or task.get("type"),
            status="failed",
            error=str(exc),
        )
        return {"task": self._normalize_task(task), "error": str(exc)}

    def _result_summary(self, result: dict[str, Any]) -> dict[str, Any]:
        report = result.get("report") if isinstance(result.get("report"), dict) else {}
        sample = result.get("sample_analysis") if isinstance(result.get("sample_analysis"), dict) else {}
        translation = result.get("translation") if isinstance(result.get("translation"), dict) else {}
        auto_translation_task = result.get("auto_translation_task") if isinstance(result.get("auto_translation_task"), dict) else {}
        summary: dict[str, Any] = {}
        if report:
            evidence = report.get("collection_evidence") if isinstance(report.get("collection_evidence"), dict) else {}
            summary["report"] = {
                "id": report.get("id"),
                "video_title": report.get("video_title"),
                "analysis_source": evidence.get("analysis_source"),
                "analysis_status": evidence.get("analysis_status"),
                "analysis_error": evidence.get("analysis_error"),
            }
        if sample:
            summary["sample_analysis"] = {"id": sample.get("id"), "status": sample.get("status")}
        if translation:
            summary["translation"] = {
                "video_id": translation.get("video_id"),
                "translated_length": translation.get("translated_length"),
                "status": translation.get("status"),
            }
        if auto_translation_task:
            summary["auto_translation_task"] = {
                "id": auto_translation_task.get("id"),
                "status": auto_translation_task.get("status"),
            }
        return summary or {"keys": sorted(result.keys())}

    def _queue_translation_for_report(self, report: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(report, dict):
            return None
        video_id = str(report.get("youtube_video_id") or "")
        if not video_id:
            return None
        task_result = self.create_task(
            "translation",
            {
                "video_id": video_id,
                "target_language": str(payload.get("target_language") or "zh-CN"),
                "force": bool(payload.get("force_translation", False)),
                "target_url": str(report.get("video_url") or payload.get("video_url") or payload.get("target_url") or ""),
                "report_id": str(report.get("id") or ""),
            },
        )
        return task_result.get("task") if isinstance(task_result.get("task"), dict) else None

    def _human_error_message(self, exc: Exception) -> str:
        message = str(exc)
        if "429" in message:
            return "YouTube rate limited the request. Wait before retrying and avoid batch downloads."
        if "ffmpeg" in message.lower():
            return "ffmpeg could not process the media sample. Check ffmpeg availability or retry later."
        if "timed out" in message.lower() or "timeout" in message.lower():
            return "The request timed out. Retry once the network or local service is stable."
        return message or exc.__class__.__name__

    def _as_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _job_ids(self) -> set[str]:
        return {str(job.get("id") or "") for job in self.store.load()["jobs"]}

    def _remove_new_jobs(self, before_ids: set[str], keep_task_id: str) -> None:
        def remove(data: dict[str, Any]) -> None:
            data["jobs"] = [
                job
                for job in data["jobs"]
                if str(job.get("id") or "") in before_ids or str(job.get("id") or "") == keep_task_id
            ]

        self.store.update(remove)

    def _steps_for(self, kind: str, current_step: str, status: str) -> list[dict[str, str]]:
        plan = TASK_STEPS.get(kind, TASK_STEPS["video_analysis"])
        keys = [key for key, _label in plan]
        current_index = keys.index(current_step) if current_step in keys else 0
        normalized = []
        for index, (key, label) in enumerate(plan):
            if status == "failed" and key == current_step:
                step_status = "failed"
            elif status == "complete" or index < current_index:
                step_status = "complete"
            elif index == current_index:
                step_status = "running" if status == "running" else status
            else:
                step_status = "pending"
            normalized.append({"key": key, "label": label, "status": step_status})
        if status == "failed" and current_step not in keys:
            normalized.append({"key": current_step, "label": current_step.replace("_", " ").title(), "status": "failed"})
        return normalized

    def _step_label(self, kind: str, current_step: str) -> str:
        for key, label in TASK_STEPS.get(kind, TASK_STEPS["video_analysis"]):
            if key == current_step:
                return label
        return current_step.replace("_", " ").title()

    def _next_task_id(self, jobs: list[dict[str, Any]]) -> str:
        existing = {str(job.get("id") or "") for job in jobs}
        task_id = unique_workspace_id("job")
        while task_id in existing:
            task_id = unique_workspace_id("job")
        return task_id
