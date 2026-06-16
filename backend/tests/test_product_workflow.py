import json

import pytest
from fastapi.testclient import TestClient

from creator_agent.main import create_app


def _write_workspace(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_task_center_lists_jobs_with_steps_and_infrastructure_status(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_REDIS_URL", "redis://localhost:6379/15")
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [],
            "sample_analyses": [],
            "jobs": [
                    {
                        "id": "job-1",
                        "kind": "sample_analysis",
                        "status": "running",
                        "current_step": "analyze_opening_script",
                        "target_url": "https://www.youtube.com/watch?v=abc123",
                        "created_at": "2026-06-09T12:00:00+00:00",
                        "updated_at": "2026-06-09T12:01:00+00:00",
                }
            ],
        },
    )
    client = TestClient(create_app())

    response = client.get("/api/tasks")

    assert response.status_code == 200
    body = response.json()
    assert body["redis"]["configured"] is True
    assert body["tasks"][0]["id"] == "job-1"
    assert body["tasks"][0]["current_step_label"]
    assert body["tasks"][0]["steps"][0]["key"] == "queued"
    assert any(step["key"] == "analyze_opening_script" for step in body["tasks"][0]["steps"])


def test_task_center_retries_failed_job_by_cloning_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [],
            "sample_analyses": [],
            "jobs": [
                {
                    "id": "job-1",
                    "kind": "video_analysis",
                    "status": "failed",
                    "current_step": "failed",
                    "target_url": "https://www.youtube.com/watch?v=abc123",
                    "error_message": "LLM request timed out",
                    "created_at": "2026-06-09T12:00:00+00:00",
                    "updated_at": "2026-06-09T12:01:00+00:00",
                }
            ],
        },
    )
    client = TestClient(create_app())

    response = client.post("/api/tasks/job-1/retry")

    assert response.status_code == 200
    task = response.json()["task"]
    assert task["status"] == "queued"
    assert task["retry_of"] == "job-1"
    assert task["target_url"] == "https://www.youtube.com/watch?v=abc123"
    listed = client.get("/api/tasks").json()["tasks"]
    assert listed[0]["id"] == task["id"]
    assert listed[0]["retry_of"] == "job-1"


def test_sample_library_updates_tags_favorite_and_merges_style(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [],
            "style_profiles": [],
            "copy_drafts": [],
            "jobs": [],
            "sample_analyses": [
                {
                    "id": "sample-1",
                    "video_url": "https://www.youtube.com/watch?v=one",
                    "video_title": "Fast story opening",
                    "status": "complete",
                    "analyzed_seconds": 300,
                    "frame_count": 3,
                    "frames": [],
                    "visual_summary": "Immediate conflict, then status reversal.",
                    "opening_hook": "A low-status character wins in the first scene.",
                    "pacing_notes": ["Cold open", "Fast reversal"],
                    "reuse_template": ["Open with visible consequence", "Delay the explanation"],
                    "risk_notes": ["Do not copy the exact plot."],
                    "created_at": "2026-06-09T12:00:00+00:00",
                },
                {
                    "id": "sample-2",
                    "video_url": "https://www.youtube.com/watch?v=two",
                    "video_title": "System payoff loop",
                    "status": "complete",
                    "analyzed_seconds": 300,
                    "frame_count": 2,
                    "frames": [],
                    "visual_summary": "Promise, system trigger, escalating rewards.",
                    "opening_hook": "The system appears before the context is fully explained.",
                    "pacing_notes": ["Reward loop", "Clear captions"],
                    "reuse_template": ["Trigger a rule", "Escalate the reward"],
                    "risk_notes": ["Avoid identical system names."],
                    "created_at": "2026-06-09T12:02:00+00:00",
                },
            ],
        },
    )
    client = TestClient(create_app())

    updated = client.patch(
        "/api/samples/sample-1",
        json={"favorite": True, "tags": ["story_recap", "system"], "notes": "Use for openings."},
    )
    merged = client.post(
        "/api/samples/merge-style",
        json={"sample_ids": ["sample-1", "sample-2"], "name": "Fast System Opening"},
    )
    library = client.get("/api/samples/library")

    assert updated.status_code == 200
    assert updated.json()["sample"]["favorite"] is True
    assert updated.json()["sample"]["tags"] == ["story_recap", "system"]
    assert merged.status_code == 200
    style = merged.json()["style_profile"]
    assert style["name"] == "Fast System Opening"
    assert style["source_sample_ids"] == ["sample-1", "sample-2"]
    assert "Open with visible consequence" in style["reusable_rules"]
    assert library.status_code == 200
    assert library.json()["samples"][0]["id"] == "sample-1"


def test_health_checks_report_required_integrations(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    monkeypatch.setenv("YCA_REDIS_URL", "redis://localhost:6379/15")
    client = TestClient(create_app())

    response = client.get("/api/health/checks")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["status"] in {"ok", "degraded", "failed"}
    checks = {item["key"]: item for item in body["checks"]}
    for key in ["mysql", "redis", "yt_dlp", "ffmpeg", "llm", "browser_cdp", "cache", "local_access"]:
        assert key in checks
        assert checks[key]["status"] in {"ok", "warning", "failed", "skipped"}
        assert checks[key]["label"]
        assert checks[key]["message"]


def test_health_checks_skip_default_redis_when_not_explicitly_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    monkeypatch.delenv("YCA_REDIS_URL", raising=False)
    client = TestClient(create_app())

    response = client.get("/api/health/checks")

    assert response.status_code == 200
    checks = {item["key"]: item for item in response.json()["checks"]}
    assert checks["redis"]["status"] == "skipped"
    assert "optional" in checks["redis"]["message"].lower()


def test_health_checks_warn_when_remote_access_is_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    monkeypatch.setenv("YCA_ALLOW_REMOTE_ACCESS", "true")
    client = TestClient(create_app())

    response = client.get("/api/health/checks")

    assert response.status_code == 200
    checks = {item["key"]: item for item in response.json()["checks"]}
    assert checks["local_access"]["status"] == "warning"
    assert "remote access" in checks["local_access"]["message"].lower()


def test_task_start_endpoint_queues_video_analysis_without_running_immediately(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    calls = []

    def fake_add_task(fn, *args, **kwargs):
        calls.append((fn.__name__, args, kwargs))

    client = TestClient(create_app())

    response = client.post(
        "/api/tasks/video-analysis/start",
        json={"video_url": "https://www.youtube.com/watch?v=abc123"},
    )
    listed = client.get("/api/tasks")

    assert response.status_code == 200
    assert response.json()["task"]["status"] == "queued"
    assert response.json()["task"]["kind"] == "video_analysis"
    assert response.json()["task"]["id"].startswith("job-")
    assert response.json()["task"]["target_url"] == "https://www.youtube.com/watch?v=abc123"
    assert listed.json()["tasks"][0]["current_step"] == "queued"
    assert calls == []


def test_task_start_generates_unique_task_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    client = TestClient(create_app())

    first = client.post("/api/tasks/video-analysis/start", json={"video_url": "https://www.youtube.com/watch?v=first"})
    second = client.post("/api/tasks/video-analysis/start", json={"video_url": "https://www.youtube.com/watch?v=second"})

    assert first.status_code == 200
    assert second.status_code == 200
    first_id = first.json()["task"]["id"]
    second_id = second.json()["task"]["id"]
    assert first_id.startswith("job-")
    assert second_id.startswith("job-")
    assert first_id != second_id


def test_task_start_marks_manual_run_when_redis_enqueue_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setattr("creator_agent.services.redis_task_queue.RedisTaskQueue.enqueue", lambda self, task_id: False)
    monkeypatch.setattr(
        "creator_agent.services.redis_task_queue.RedisTaskQueue.status",
        lambda self: {"configured": True, "status": "failed", "message": "Redis unavailable.", "queued_count": 0},
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/tasks/video-analysis/start",
        json={"video_url": "https://www.youtube.com/watch?v=abc123"},
    )

    assert response.status_code == 200
    task = response.json()["task"]
    assert response.json()["enqueued"] is False
    assert task["status"] == "queued"
    assert task["queue_status"] == "not_enqueued"
    assert "run this task manually" in task["queue_message"]


def test_task_runner_executes_channel_sync_and_updates_original_task(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    monkeypatch.setattr(
        "creator_agent.services.workspace_store.get_channel_recent_videos",
        lambda channel_id, channel_url: {
            "collection_status": "ok",
            "videos": [
                {
                    "youtube_video_id": "abc123",
                    "title": "Queued sync video",
                    "url": "https://www.youtube.com/watch?v=abc123",
                    "published_text": "today",
                    "view_count": 1234,
                }
            ],
        },
    )
    client = TestClient(create_app())
    client.put(
        "/api/settings",
        json={
            "channel_url": "https://www.youtube.com/@growthlab",
            "channel_urls": ["https://www.youtube.com/@growthlab"],
            "browser_engine": "playwright",
            "browser_headless": True,
            "browser_path": "",
            "browser_debug_port": None,
            "browser_cdp_url": "http://127.0.0.1:9222",
            "openai_base_url": "http://localhost:53881/v1",
            "openai_translation_model": "gpt-5.5",
            "openai_analysis_model": "gpt-5.5",
            "openai_api_key": "",
            "openai_api_key_set": False,
            "monitor_enabled": True,
            "monitor_interval_minutes": 180,
            "monitor_auto_analyze": False,
            "monitor_auto_translate": False,
            "monitor_min_views": 1000,
        },
    )

    queued = client.post("/api/tasks/channel-sync/start").json()["task"]
    from creator_agent.services.task_service import TaskService

    result = TaskService().run_task(queued["id"])
    listed = client.get("/api/tasks").json()["tasks"]
    dashboard = client.get("/api/dashboard").json()

    assert result["task"]["status"] == "complete"
    assert listed[0]["id"] == queued["id"]
    assert listed[0]["current_step"] == "complete"
    assert dashboard["recent_videos"][0]["title"] == "Queued sync video"


def test_task_runner_skips_already_claimed_task_without_executing(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [],
            "sample_analyses": [],
            "jobs": [
                {
                    "id": "job-1",
                    "kind": "channel_sync",
                    "status": "running",
                    "current_step": "collect_channel",
                    "created_at": "2026-06-09T12:00:00+00:00",
                    "updated_at": "2026-06-09T12:01:00+00:00",
                }
            ],
        },
    )

    def fail_sync(self):
        raise AssertionError("already running task should not execute twice")

    monkeypatch.setattr("creator_agent.services.workspace_store.WorkspaceStore.sync_channel", fail_sync)
    from creator_agent.services.task_service import TaskService

    result = TaskService().run_task("job-1")

    assert result["skipped"] is True
    assert result["reason"] == "Task is not queued."
    assert result["task"]["status"] == "running"


def test_redis_queue_worker_runs_next_queued_task(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    queued_ids = []

    def fake_enqueue(self, task_id):
        queued_ids.append(task_id)
        return True

    def fake_dequeue(self, timeout_seconds=0):
        return queued_ids.pop(0) if queued_ids else None

    monkeypatch.setattr("creator_agent.services.redis_task_queue.RedisTaskQueue.enqueue", fake_enqueue)
    monkeypatch.setattr("creator_agent.services.redis_task_queue.RedisTaskQueue.dequeue", fake_dequeue)
    monkeypatch.setattr(
        "creator_agent.services.redis_task_queue.RedisTaskQueue.status",
        lambda self: {"configured": True, "status": "ok", "message": "Redis queue is reachable.", "queued_count": len(queued_ids)},
    )
    monkeypatch.setattr("creator_agent.services.workspace_store.WorkspaceStore.sync_channel", lambda self: {"synced": True})
    client = TestClient(create_app())

    queued = client.post("/api/tasks/channel-sync/start").json()
    ran = client.post("/api/tasks/worker/run-next")
    listed = client.get("/api/tasks").json()

    assert queued["enqueued"] is True
    assert ran.status_code == 200
    assert ran.json()["task"]["status"] == "complete"
    assert listed["queue"]["queued_count"] == 0
    assert listed["tasks"][0]["current_step"] == "complete"


def test_task_queue_writes_audit_events(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_ANALYSIS_LOG_PATH", str(tmp_path / "analysis.jsonl"))
    queued_ids = []

    def fake_enqueue(self, task_id):
        queued_ids.append(task_id)
        return True

    def fake_dequeue(self, timeout_seconds=0):
        return queued_ids.pop(0) if queued_ids else None

    monkeypatch.setattr("creator_agent.services.redis_task_queue.RedisTaskQueue.enqueue", fake_enqueue)
    monkeypatch.setattr("creator_agent.services.redis_task_queue.RedisTaskQueue.dequeue", fake_dequeue)
    monkeypatch.setattr(
        "creator_agent.services.redis_task_queue.RedisTaskQueue.status",
        lambda self: {"configured": True, "status": "ok", "message": "Redis queue is reachable.", "queued_count": len(queued_ids)},
    )
    monkeypatch.setattr("creator_agent.services.workspace_store.WorkspaceStore.sync_channel", lambda self: {"synced": True})
    client = TestClient(create_app())

    queued = client.post("/api/tasks/channel-sync/start").json()["task"]
    client.post("/api/tasks/worker/run-next")

    text = (tmp_path / "analysis.jsonl").read_text(encoding="utf-8")
    assert '"event": "task_queued"' in text
    assert '"event": "task_claimed"' in text
    assert '"event": "task_finished"' in text
    assert queued["id"] in text


def test_worker_skips_stale_queue_items_without_exiting(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_ANALYSIS_LOG_PATH", str(tmp_path / "analysis.jsonl"))
    queued_ids = ["missing-task"]
    monitor_calls = []

    def fake_dequeue(self, timeout_seconds=1):
        return queued_ids.pop(0) if queued_ids else None

    monkeypatch.setattr("creator_agent.services.redis_task_queue.RedisTaskQueue.dequeue", fake_dequeue)
    monkeypatch.setattr("creator_agent.services.task_service.TaskService.run_task", lambda self, task_id, from_queue=False: (_ for _ in ()).throw(ValueError("Task not found.")))
    monkeypatch.setattr("creator_agent.services.monitor_service.MonitorService.run_if_due", lambda self: monitor_calls.append("monitor"))

    from creator_agent.worker import run_worker

    run_worker(once=True)

    text = (tmp_path / "analysis.jsonl").read_text(encoding="utf-8")
    assert '"event": "worker_skipped_stale_task"' in text
    assert "missing-task" in text


def test_video_analysis_task_records_granular_progress_steps(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    seen_steps = []

    def fake_analyze(self, video_url, progress_callback=None):
        assert callable(progress_callback)
        for step in ["metadata", "transcript", "comments", "llm_analysis", "save_report"]:
            progress_callback(step)
            seen_steps.append(self.load()["jobs"][0]["current_step"])
        return {"job": {"status": "complete"}, "report": {"id": "report-1"}}

    monkeypatch.setattr("creator_agent.services.workspace_store.WorkspaceStore.analyze_video", fake_analyze)
    client = TestClient(create_app())
    queued = client.post(
        "/api/tasks/video-analysis/start",
        json={"video_url": "https://www.youtube.com/watch?v=abc123"},
    ).json()["task"]

    from creator_agent.services.task_service import TaskService

    result = TaskService().run_task(queued["id"])

    assert result["task"]["status"] == "complete"
    assert seen_steps == ["metadata", "transcript", "comments", "llm_analysis", "save_report"]


def test_report_translation_start_queues_task_without_calling_llm(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [
                {
                    "id": "report-1",
                    "youtube_video_id": "video-1",
                    "video_url": "https://www.youtube.com/watch?v=video-1",
                    "video_title": "Video 1",
                    "summary": "Report summary",
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )

    def fail_translation(*args, **kwargs):
        raise AssertionError("translation should be queued, not executed synchronously")

    monkeypatch.setattr(
        "creator_agent.services.translation_service.TranslationService.start_background_translation",
        fail_translation,
    )
    client = TestClient(create_app())

    response = client.post("/api/tasks/reports/report-1/translation/start", json={"force": True})
    tasks = client.get("/api/tasks").json()["tasks"]

    assert response.status_code == 200
    task = response.json()["task"]
    assert task["kind"] == "translation"
    assert task["status"] == "queued"
    assert task["target_url"] == "https://www.youtube.com/watch?v=video-1"
    assert task["payload"]["video_id"] == "video-1"
    assert task["payload"]["target_language"] == "zh-CN"
    assert task["payload"]["force"] is True
    assert tasks[0]["id"] == task["id"]


def test_translation_task_records_load_llm_and_save_steps(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    seen_steps = []

    def fake_translation(self, video_id, target_language="zh-CN", force=False):
        return {"video_id": video_id, "target_language": target_language, "translated_text": "中文"}

    monkeypatch.setattr(
        "creator_agent.services.translation_service.TranslationService.get_or_translate",
        fake_translation,
    )
    from creator_agent.services.task_service import TaskService

    original_update_task = TaskService._update_task

    def record_update(self, task_id, **updates):
        if "current_step" in updates:
            seen_steps.append(updates["current_step"])
        return original_update_task(self, task_id, **updates)

    monkeypatch.setattr(TaskService, "_update_task", record_update)
    service = TaskService()
    queued = service.create_task(
        "translation",
        {"video_id": "video-1", "target_language": "zh-CN", "force": False},
    )
    result = service.run_task(queued["task"]["id"])

    assert result["task"]["status"] == "complete"
    assert seen_steps == ["load_transcript", "llm_translation", "save_translation", "complete"]


def test_video_analysis_task_can_queue_translation_after_analysis(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_TRANSCRIPT_CACHE_DIR", str(tmp_path / "transcripts"))
    monkeypatch.setenv("YCA_TRANSLATION_CACHE_DIR", str(tmp_path / "translations"))
    queued_ids = []

    def fake_enqueue(self, task_id):
        queued_ids.append(task_id)
        return True

    monkeypatch.setattr("creator_agent.services.redis_task_queue.RedisTaskQueue.enqueue", fake_enqueue)
    monkeypatch.setattr(
        "creator_agent.services.redis_task_queue.RedisTaskQueue.status",
        lambda self: {"configured": True, "status": "ok", "message": "Redis queue is reachable.", "queued_count": len(queued_ids)},
    )
    monkeypatch.setattr(
        "creator_agent.agent.runtime.AgentRuntime.run_video_analysis",
        lambda self, video_url, progress_callback=None: type(
            "FakeResult",
            (),
            {
                "tool_results": {
                    "get_video_metadata": {
                        "youtube_video_id": "video-1",
                        "title": "Auto translated video",
                        "channel": {"title": "Growth Lab"},
                    },
                    "get_transcript": {"text": "story text", "source": "caption", "language": "en"},
                    "analyze_with_llm": {"source": "llm", "status": "ok"},
                },
                "report": type(
                    "FakeReport",
                    (),
                    {
                        "model_dump": lambda self: {
                            "summary": "summary",
                            "creative_breakdown": {"title_hook": "hook", "opening_hook": "opening", "structure": [], "emotional_curve": []},
                            "growth_judgement": {"score": 80, "reasons": []},
                            "idea_cards": [],
                            "comment_insights": {"status": "not_configured"},
                        }
                    },
                )(),
            },
        )(),
    )

    from creator_agent.services.task_service import TaskService

    service = TaskService()
    queued = service.create_task(
        "video_analysis",
        {
            "video_url": "https://www.youtube.com/watch?v=video-1",
            "auto_translate": True,
            "target_language": "zh-CN",
        },
    )
    result = service.run_task(queued["task"]["id"])
    tasks = service.list_tasks()["tasks"]
    translation_task = next(task for task in tasks if task["kind"] == "translation")

    assert result["task"]["status"] == "complete"
    assert result["result"]["auto_translation_task"]["id"] == translation_task["id"]
    assert translation_task["payload"]["video_id"] == "video-1"
    assert translation_task["payload"]["target_language"] == "zh-CN"


def test_settings_endpoint_saves_monitoring_controls(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    client = TestClient(create_app())

    response = client.put(
        "/api/settings",
        json={
            "channel_url": "https://www.youtube.com/@growthlab",
            "channel_urls": ["https://www.youtube.com/@growthlab"],
            "browser_engine": "playwright",
            "browser_headless": True,
            "browser_path": "",
            "browser_debug_port": None,
            "browser_cdp_url": "http://127.0.0.1:9222",
            "openai_base_url": "http://localhost:53881/v1",
            "openai_translation_model": "gpt-5.5",
            "openai_analysis_model": "gpt-5.5",
            "openai_api_key": "",
            "openai_api_key_set": False,
            "monitor_enabled": True,
            "monitor_interval_minutes": 240,
            "monitor_auto_analyze": True,
            "monitor_auto_translate": True,
            "monitor_min_views": 50000,
        },
    )
    saved = client.get("/api/settings")

    assert response.status_code == 200
    assert saved.json()["monitor_enabled"] is True
    assert saved.json()["monitor_interval_minutes"] == 240
    assert saved.json()["monitor_auto_analyze"] is True
    assert saved.json()["monitor_auto_translate"] is True
    assert saved.json()["monitor_min_views"] == 50000


def test_auto_monitor_syncs_channel_and_queues_threshold_matches(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    queued_ids = []

    def fake_enqueue(self, task_id):
        queued_ids.append(task_id)
        return True

    monkeypatch.setattr("creator_agent.services.redis_task_queue.RedisTaskQueue.enqueue", fake_enqueue)
    monkeypatch.setattr(
        "creator_agent.services.redis_task_queue.RedisTaskQueue.status",
        lambda self: {"configured": True, "status": "ok", "message": "Redis queue is reachable.", "queued_count": len(queued_ids)},
    )
    monkeypatch.setattr(
        "creator_agent.services.workspace_store.get_channel_recent_videos",
        lambda channel_id, channel_url: {
            "collection_status": "ok",
            "videos": [
                {
                    "youtube_video_id": "hot-video",
                    "title": "Hot upload",
                    "url": "https://www.youtube.com/watch?v=hot",
                    "published_text": "1 hour ago",
                    "view_count": 90000,
                },
                {
                    "youtube_video_id": "small-video",
                    "title": "Small upload",
                    "url": "https://www.youtube.com/watch?v=small",
                    "published_text": "2 hours ago",
                    "view_count": 1200,
                },
            ],
        },
    )
    client = TestClient(create_app())
    client.put(
        "/api/settings",
        json={
            "channel_url": "https://www.youtube.com/@growthlab",
            "channel_urls": ["https://www.youtube.com/@growthlab"],
            "browser_engine": "playwright",
            "browser_headless": True,
            "browser_path": "",
            "browser_debug_port": None,
            "browser_cdp_url": "http://127.0.0.1:9222",
            "openai_base_url": "http://localhost:53881/v1",
            "openai_translation_model": "gpt-5.5",
            "openai_analysis_model": "gpt-5.5",
            "openai_api_key": "",
            "openai_api_key_set": False,
            "monitor_enabled": True,
            "monitor_interval_minutes": 180,
            "monitor_auto_analyze": True,
            "monitor_auto_translate": False,
            "monitor_min_views": 50000,
        },
    )

    response = client.post("/api/monitor/run")
    body = response.json()
    dashboard = client.get("/api/dashboard").json()
    tasks = client.get("/api/tasks").json()

    assert response.status_code == 200
    assert body["status"] == "complete"
    assert body["new_video_count"] == 2
    assert body["queued_analysis_count"] == 1
    assert body["skipped_analysis_count"] == 1
    assert dashboard["recent_videos"][0]["title"] == "Hot upload"
    assert tasks["tasks"][0]["kind"] == "video_analysis"
    assert tasks["tasks"][0]["target_url"] == "https://www.youtube.com/watch?v=hot"
    assert queued_ids == [tasks["tasks"][0]["id"]]


def test_auto_monitor_does_not_run_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    client = TestClient(create_app())
    client.put(
        "/api/settings",
        json={
            "channel_url": "https://www.youtube.com/@growthlab",
            "channel_urls": ["https://www.youtube.com/@growthlab"],
            "browser_engine": "playwright",
            "browser_headless": True,
            "browser_path": "",
            "browser_debug_port": None,
            "browser_cdp_url": "http://127.0.0.1:9222",
            "openai_base_url": "http://localhost:53881/v1",
            "openai_translation_model": "gpt-5.5",
            "openai_analysis_model": "gpt-5.5",
            "openai_api_key": "",
            "openai_api_key_set": False,
            "monitor_enabled": False,
            "monitor_interval_minutes": 180,
            "monitor_auto_analyze": True,
            "monitor_auto_translate": False,
            "monitor_min_views": 0,
        },
    )

    response = client.post("/api/monitor/run")

    assert response.status_code == 200
    assert response.json()["status"] == "skipped"
    assert response.json()["reason"] == "Auto monitor is disabled."


def test_cache_risk_endpoint_reports_paths_and_can_clear_samples(tmp_path, monkeypatch):
    sample_dir = tmp_path / "samples"
    transcript_dir = tmp_path / "transcripts"
    translation_dir = tmp_path / "translations"
    sample_dir.mkdir()
    transcript_dir.mkdir()
    translation_dir.mkdir()
    (sample_dir / "frame.jpg").write_text("image", encoding="utf-8")
    (transcript_dir / "abc.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("YCA_SAMPLE_CACHE_DIR", str(sample_dir))
    monkeypatch.setenv("YCA_TRANSCRIPT_CACHE_DIR", str(transcript_dir))
    monkeypatch.setenv("YCA_TRANSLATION_CACHE_DIR", str(translation_dir))
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    client = TestClient(create_app())

    before = client.get("/api/cache")
    cleared = client.post("/api/cache/clear", json={"target": "samples"})
    after = client.get("/api/cache")

    assert before.status_code == 200
    assert before.json()["policy"]["retains_full_video"] is False
    assert before.json()["paths"]["samples"]["file_count"] == 1
    assert cleared.status_code == 200
    assert cleared.json()["cleared"]["target"] == "samples"
    assert after.json()["paths"]["samples"]["file_count"] == 0
    assert after.json()["paths"]["transcripts"]["file_count"] == 1


def test_workspace_store_backs_up_corrupt_json_before_failing(tmp_path, monkeypatch):
    data_path = tmp_path / "workspace-data.json"
    data_path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(data_path))

    from creator_agent.services.workspace_store import WorkspaceStore

    with pytest.raises(RuntimeError, match="invalid JSON"):
        WorkspaceStore().load()

    assert not data_path.exists()
    backups = list(tmp_path.glob("workspace-data.json.corrupt-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{not-json"
