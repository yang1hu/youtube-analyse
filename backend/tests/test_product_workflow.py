import json
import sys
from datetime import UTC, datetime

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


def test_style_library_merges_multiple_reports_into_reusable_style(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "style_profiles": [],
            "copy_drafts": [],
            "sample_analyses": [],
            "jobs": [],
            "reports": [
                {
                    "id": "report-1",
                    "video_title": "System payoff",
                    "video_url": "https://www.youtube.com/watch?v=one",
                    "summary": "A nobody triggers a hidden reward.",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "No one knew the rule.",
                        "opening_hook": "Open with public pressure.",
                        "structure": ["Public pressure", "Hidden trigger", "First payoff"],
                        "emotional_curve": ["Pressure", "Curiosity", "Payoff"],
                    },
                    "growth_judgement": {"score": 90, "reasons": ["Strong information gap"]},
                },
                {
                    "id": "report-2",
                    "video_title": "Public reversal",
                    "video_url": "https://www.youtube.com/watch?v=two",
                    "summary": "A low-status hero wins publicly.",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "Everyone misread the hero.",
                        "opening_hook": "Start from visible humiliation.",
                        "structure": ["Visible humiliation", "First payoff", "Public reversal"],
                        "emotional_curve": ["Pressure", "Payoff", "Suspense"],
                    },
                    "growth_judgement": {"score": 88, "reasons": ["Clear public reversal"]},
                },
            ],
        },
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/styles/merge-reports",
        json={"report_ids": ["report-1", "report-2"], "name": "Merged story engine"},
    )
    styles = client.get("/api/styles").json()["style_profiles"]

    assert response.status_code == 200
    style = response.json()["style_profile"]
    assert style["name"] == "Merged story engine"
    assert style["topic_type"] == "multi_report_merge"
    assert style["source_report_ids"] == ["report-1", "report-2"]
    assert "First payoff" in style["rhythm_formula"]
    assert style["reusable_rules"]
    assert styles[0]["id"] == style["id"]


def test_imitation_factory_builds_inkos_reference_package(tmp_path, monkeypatch):
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
                    "video_title": "Original story recap",
                    "summary": "A low-status hero triggers a hidden reward loop.",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "Everyone underestimated the hidden rule.",
                        "opening_hook": "Open on public humiliation before explaining the system.",
                        "structure": ["Public pressure", "Tiny trigger", "First payoff", "Bigger reversal"],
                        "emotional_curve": ["Pressure", "Curiosity", "Payoff", "Suspense"],
                    },
                    "growth_judgement": {
                        "score": 88,
                        "reasons": ["Strong information gap", "Clear public payoff"],
                    },
                    "idea_cards": [
                        {
                            "title": "Hidden reward loop in a new setting",
                            "angle": "Turn a small kindness into a status reversal.",
                            "why_it_works": "The audience waits for the public payoff.",
                            "outline": ["Show the consequence", "Reveal the hidden rule"],
                            "risk_notes": "Change the reward names and scene order.",
                        }
                    ],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "idea_id": "report-1-idea-1",
            "direction": "鍐欐垚涓€涓幇浠ｉ兘甯傜煭鐗囧皬璇达紝涓昏鏄浣庝及鐨勫疄涔犵敓銆?",
            "output_type": "short_fiction",
            "similarity_level": "high",
            "target_length": "3000 Chinese characters",
            "keep_narration": True,
        },
    )
    listed = client.get("/api/imitation-factory")

    assert response.status_code == 200
    project = response.json()["project"]
    assert project["id"].startswith("imitate-")
    assert project["source_report_id"] == "report-1"
    assert project["risk_level"] == "needs_review"
    assert "inkos short run" in project["inkos_command"]
    assert "InkOS 创作转化参考包" in project["reference_markdown"]
    assert "Hidden reward loop in a new setting" in project["reference_markdown"]
    assert "不可复用内容" in project["reference_markdown"]
    assert "避抄边界" in project["reference_markdown"]
    assert "??" not in project["reference_markdown"]
    assert "??" not in project["reference_markdown"]
    assert "规避检测" not in project["reference_markdown"]
    assert "Public pressure" in project["structure_template"]
    assert project["inkos_preview"]["reference_length"] == len(project["reference_markdown"])
    assert project["inkos_preview"]["estimated_total_tokens"] > project["inkos_preview"]["estimated_input_tokens"]
    assert project["inkos_preview"]["similarity_level"] == "high"
    assert project["inkos_preview"]["risk_notes"]
    assert listed.status_code == 200
    assert listed.json()["projects"][0]["id"] == project["id"]
    assert listed.json()["reports"][0]["id"] == "report-1"


def test_imitation_factory_applies_favorite_structure_template(tmp_path, monkeypatch):
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
                    "video_title": "Template target",
                    "summary": "summary",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "hook",
                        "opening_hook": "opening",
                        "structure": ["Report structure"],
                        "emotional_curve": [],
                    },
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "favorite_structure_templates": [
                {
                    "id": "template-1",
                    "source_project_id": "imitate-old",
                    "name": "Public payoff engine",
                    "source_video_title": "Old source",
                    "structure_template": ["Template pressure", "Template reveal", "Template payoff"],
                    "reuse_constraints": ["淇濈暀鍏紑鍏戠幇"],
                    "anti_copy_rules": ["Avoid copying source entities"],
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "template_id": "template-1",
            "direction": "鎹㈡垚鏍″洯鏁呬簨銆?",
            "output_type": "short_fiction",
            "similarity_level": "medium",
            "target_length": "3000 Chinese characters",
            "keep_narration": True,
        },
    )

    assert response.status_code == 200
    project = response.json()["project"]
    assert project["source_template_id"] == "template-1"
    assert project["source_template_name"] == "Public payoff engine"
    assert project["structure_template"] == ["Template pressure", "Template reveal", "Template payoff"]
    assert project["reuse_constraints"]
    assert "Avoid copying source entities" in project["anti_copy_rules"]
    assert "Public payoff engine" in project["reference_markdown"]


def test_imitation_factory_applies_style_profile_to_reference_package(tmp_path, monkeypatch):
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
                    "video_title": "Style source story",
                    "summary": "A fast public reversal.",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "No one expected the reveal.",
                        "opening_hook": "Open with visible consequence.",
                        "structure": ["Pressure", "Hidden rule", "Public payoff"],
                        "emotional_curve": ["Pressure", "Curiosity", "Payoff"],
                    },
                    "growth_judgement": {"score": 82, "reasons": ["Clear rhythm"]},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "style_profiles": [
                {
                    "id": "style-1",
                    "name": "Fast public reversal voice",
                    "source_video_title": "Style source story",
                    "topic_type": "story_recap",
                    "opening_formula": "鍏堢粰鍏紑鍚庢灉锛屽啀瑙ｉ噴闅愯棌瑙勫垯銆?",
                    "title_formula": "浣庝及 -> 瑙﹀彂 -> 鍏紑鍙嶈浆",
                    "rhythm_formula": ["pressure", "reveal", "payoff"],
                    "emotional_engine": ["鍘嬭揩", "濂藉", "鐖界偣"],
                    "sentence_style": "鐭彞鎺ㄨ繘锛屾瘡娈靛彧鎺ㄨ繘涓€涓俊鎭樊銆?",
                    "reusable_rules": ["reuse rhythm only"],
                    "avoid_copying": ["avoid source entities"],
                    "created_at": "2026-06-09T12:05:00+00:00",
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "style_id": "style-1",
            "direction": "鎹㈡垚鏍″洯鐭墖灏忚銆?",
            "output_type": "short_fiction",
            "similarity_level": "medium",
            "target_length": "3000 Chinese characters",
            "keep_narration": True,
        },
    )
    listed = client.get("/api/imitation-factory")

    assert response.status_code == 200
    project = response.json()["project"]
    assert project["source_style_id"] == "style-1"
    assert project["source_style_name"] == "Fast public reversal voice"
    assert project["source_style_profile"]["sentence_style"] == "鐭彞鎺ㄨ繘锛屾瘡娈靛彧鎺ㄨ繘涓€涓俊鎭樊銆?"
    assert "## 风格包约束" in project["reference_markdown"]
    assert "Fast public reversal voice" in project["reference_markdown"]
    assert "avoid source entities" in project["reference_markdown"]
    assert "reuse rhythm only" in project["reuse_constraints"]
    assert "avoid source entities" in project["anti_copy_rules"]
    assert listed.json()["styles"][0]["id"] == "style-1"


def test_imitation_factory_reports_inkos_status(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    fake_inkos = tmp_path / "fake_inkos.py"
    fake_inkos.write_text("print('ok')", encoding="utf-8")
    monkeypatch.setenv("YCA_INKOS_COMMAND", f'"{sys.executable}" "{fake_inkos}"')
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [],
            "sample_analyses": [],
            "imitation_projects": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    response = client.get("/api/imitation-factory")

    assert response.status_code == 200
    status = response.json()["inkos_status"]
    assert status["configured"] is True
    assert status["executable"].strip('"') == sys.executable
    assert status["project_dir"]


def test_story_workbench_cleans_transcript_and_analyzes_short_story_structure(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_TRANSCRIPT_CACHE_DIR", str(tmp_path / "transcripts"))
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
                    "video_title": "Intern reward story",
                    "summary": "An underestimated intern triggers a hidden system reward.",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "No one knew the intern had a hidden rule.",
                        "opening_hook": "Start with public humiliation.",
                        "structure": ["Public humiliation", "Hidden trigger", "First reward", "Public reversal"],
                        "emotional_curve": ["Pressure", "Curiosity", "Payoff", "Suspense"],
                    },
                    "growth_judgement": {"score": 90, "reasons": ["Information gap"]},
                    "idea_cards": [
                        {
                            "title": "Intern hidden reward",
                            "angle": "A low-status intern is publicly underestimated.",
                            "why_it_works": "The audience waits for the public payoff.",
                            "risk_notes": "Change company names.",
                        }
                    ],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    from creator_agent.services.transcript_store import TranscriptStore

    TranscriptStore().save_transcript(
        video_id="video-1",
        video_url="https://www.youtube.com/watch?v=video-1",
        title="Intern reward story",
        source="caption",
        language="zh-CN",
        raw_text="[Music] 0:01 鎵€鏈変汉閮界灖涓嶈捣杩欎釜瀹炰範鐢熴€?鎵€鏈変汉閮界灖涓嶈捣杩欎釜瀹炰範鐢熴€?鐩村埌浠栬Е鍙戦殣钘忕郴缁熷鍔便€?鍏ㄥ満閮芥矇榛樹簡銆?",
    )
    client = TestClient(create_app())

    response = client.get("/api/story-workbench/reports/report-1")

    assert response.status_code == 200
    item = response.json()["story_workbench"]
    assert "Music" not in item["cleaned_text"]
    assert item["cleanup_stats"]["duplicate_sentence_count"] >= 0
    assert item["cleanup_stats"]["raw_length"] > item["cleanup_stats"]["cleaned_length"]
    assert item["cleanup_stats"]["noise_marker_count"] >= 2
    assert item["cleanup_stats"]["duplicate_sentence_count"] >= 0
    assert item["cleanup_stats"]["segment_count"] == len(item["segments"])
    assert item["cleanup_stats"]["quality_score"] < 100
    assert item["cleanup_stats"]["quality_status"] in {"ready", "needs_review"}
    assert item["cleanup_stats"]["manual_review_reasons"]
    assert item["cleanup_changes"]["removed_noise"]
    assert isinstance(item["cleanup_changes"]["removed_duplicates"], list)
    assert item["cleanup_changes"]["removed_noise"][0]["reason"] == "subtitle_noise"
    if item["cleanup_changes"]["removed_duplicates"]:
        assert item["cleanup_changes"]["removed_duplicates"][0]["reason"] == "duplicate_sentence"
    assert item["cleanup_changes"]["sentence_break_changes"]
    assert item["analysis"]["opening_5s_hook"]
    assert item["analysis"]["evidence"]["opening_5s_hook"]["segment_indexes"] == [1]
    assert item["analysis"]["evidence"]["opening_5s_hook"]["excerpts"][0]
    assert item["analysis"]["evidence"]["first_30s_retention"]["excerpts"]
    assert item["analysis"]["protagonist_position"]
    assert item["analysis"]["public_reversal"]
    assert item["analysis"]["structure_confidence"] in {"medium", "high"}


def test_story_workbench_saves_user_cleaned_script_and_reanalyzes(tmp_path, monkeypatch):
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
                    "video_title": "Manual clean story",
                    "summary": "summary",
                    "creative_breakdown": {"structure": [], "emotional_curve": []},
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    saved = client.put(
        "/api/story-workbench/reports/report-1",
        json={"cleaned_text": "Opening pressure.\nHidden rule pays off.\nEnding suspense."},
    )
    fetched = client.get("/api/story-workbench/reports/report-1")

    assert saved.status_code == 200
    item = saved.json()["story_workbench"]
    assert item["cleaned_length"] > 0
    assert item["segments"][0]["label_key"] == "opening_hook"
    assert item["analysis"]["first_payoff"]
    assert fetched.json()["story_workbench"]["cleaned_text"] == item["cleaned_text"]


def test_story_workbench_manual_structure_edits_feed_creation_package(tmp_path, monkeypatch):
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
                    "video_title": "Editable story",
                    "summary": "summary",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "hook",
                        "opening_hook": "report opening",
                        "structure": ["Original auto structure"],
                        "emotional_curve": [],
                    },
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())
    client.put(
        "/api/story-workbench/reports/report-1",
        json={"cleaned_text": "Low-status hero is misunderstood.\nHidden rule pays off.\nEnding raises the cost."},
    )

    updated = client.patch(
        "/api/story-workbench/reports/report-1/analysis",
        json={
            "opening_5s_hook": "Manual hook: public misunderstanding first.",
            "first_30s_retention": "Manual retention: hidden rule appears quickly.",
            "reusable_template": ["manual opening", "manual payoff", "manual suspense"],
            "non_reusable_content": ["Do not reuse source character names", "Do not reuse source system names"],
            "structure_confidence": "high",
        },
    )
    created = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "direction": "鎹㈡垚閮藉競鐭墖灏忚銆?",
            "output_type": "short_fiction",
            "similarity_level": "medium",
            "target_length": "3000 Chinese characters",
            "keep_narration": True,
        },
    )

    assert updated.status_code == 200
    item = updated.json()["story_workbench"]
    assert item["analysis"]["manual_override"] is True
    assert item["analysis"]["opening_5s_hook"] == "Manual hook: public misunderstanding first."
    assert item["analysis"]["reusable_template"] == ["manual opening", "manual payoff", "manual suspense"]
    assert item["analysis"]["non_reusable_content"] == ["Do not reuse source character names", "Do not reuse source system names"]
    assert created.status_code == 200
    project = created.json()["project"]
    assert project["story_workbench_analysis"]["manual_override"] is True
    assert project["structure_template"] == ["manual opening", "manual payoff", "manual suspense"]
    assert "Manual hook: public misunderstanding first." in project["reference_markdown"]
    assert "Do not reuse source system names" in project["reference_markdown"]


def test_story_workbench_keeps_cleaned_script_versions(tmp_path, monkeypatch):
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
                    "video_title": "Versioned story",
                    "summary": "summary",
                    "creative_breakdown": {"structure": [], "emotional_curve": []},
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    first = client.put(
        "/api/story-workbench/reports/report-1",
        json={"cleaned_text": "First version opening.\nFirst payoff."},
    )
    second = client.put(
        "/api/story-workbench/reports/report-1",
        json={"cleaned_text": "Second version stronger opening.\nClearer first payoff.\nEnding suspense."},
    )
    duplicate = client.put(
        "/api/story-workbench/reports/report-1",
        json={"cleaned_text": "Second version stronger opening.\nClearer first payoff.\nEnding suspense."},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    versions = duplicate.json()["story_workbench"]["cleaned_versions"]
    assert [version["version"] for version in versions] == [2, 1]
    assert versions[0]["cleaned_text"].startswith("Second version")
    assert versions[1]["cleaned_text"].startswith("First version")
    assert versions[0]["segment_count"] == 3
    assert isinstance(versions[0]["quality_score"], int)
    assert versions[0]["quality_status"] in {"ready", "needs_review", "poor"}
    assert len(versions) == 2


def test_story_workbench_restores_cleaned_script_version(tmp_path, monkeypatch):
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
                    "video_title": "Restore story",
                    "summary": "summary",
                    "creative_breakdown": {"structure": [], "emotional_curve": []},
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    first = client.put(
        "/api/story-workbench/reports/report-1",
        json={"cleaned_text": "First version opening.\nFirst payoff."},
    )
    client.put(
        "/api/story-workbench/reports/report-1",
        json={"cleaned_text": "Second version stronger opening.\nClearer first payoff.\nEnding suspense."},
    )
    first_version_id = first.json()["story_workbench"]["cleaned_versions"][0]["id"]
    restored = client.post(f"/api/story-workbench/reports/report-1/versions/{first_version_id}/restore")
    fetched = client.get("/api/story-workbench/reports/report-1")

    assert restored.status_code == 200
    item = restored.json()["story_workbench"]
    assert item["cleaned_text"].startswith("First version")
    assert item["cleaned_versions"][0]["source"] == "restore:1"
    assert item["cleaned_versions"][0]["cleaned_text"].startswith("First version")
    assert item["cleaned_versions"][1]["cleaned_text"].startswith("Second version")
    assert fetched.json()["story_workbench"]["cleaned_text"].startswith("First version")


def test_imitation_factory_prefers_saved_cleaned_story_script(tmp_path, monkeypatch):
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
                    "video_title": "Cleaned source",
                    "summary": "summary",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "hook",
                        "opening_hook": "opening",
                        "structure": [],
                        "emotional_curve": [],
                    },
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "story_workbench_items": [
                {
                    "report_id": "report-1",
                    "cleaned_text": "鐢ㄦ埛绮句慨鍚庣殑寮€鍦烘枃妗堛€俓n闅愯棌瑙勫垯鍑虹幇骞跺畬鎴愮涓€娆″厬鐜般€?",
                    "segments": [],
                    "analysis": {},
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "direction": "鎹㈡垚鏍″洯鐭墖灏忚銆?",
            "output_type": "short_fiction",
            "similarity_level": "medium",
            "target_length": "3000 Chinese characters",
            "keep_narration": True,
        },
    )

    assert response.status_code == 200
    project = response.json()["project"]
    assert project["source_script_excerpt"]
    assert project["source_script_excerpt"] in project["reference_markdown"]


def test_imitation_factory_uses_story_workbench_structure_analysis(tmp_path, monkeypatch):
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
                    "video_title": "Story workbench source",
                    "summary": "summary",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "hook",
                        "opening_hook": "report opening",
                        "structure": ["Report structure should be replaced"],
                        "emotional_curve": ["Pressure", "Payoff"],
                    },
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "story_workbench_items": [
                {
                    "report_id": "report-1",
                    "cleaned_text": "娓呮礂鍚庣殑鏁呬簨绋裤€俓n闅愯棌瑙勫垯鍑虹幇銆俓n鍏紑鍏戠幇銆?",
                    "segments": [],
                    "analysis": {
                        "opening_5s_hook": "Hero is publicly misunderstood.",
                        "first_30s_retention": "Hidden rule appears quickly.",
                        "protagonist_position": "Low-status hero.",
                        "status_gap": "Public status gap.",
                        "first_payoff": "First reward pays off.",
                        "middle_escalation": "Opposition escalates.",
                        "opposition_design": "Public doubters.",
                        "public_reversal": "Public reversal.",
                        "ending_suspense": "Bigger threat remains.",
                        "reusable_template": ["workbench low opening", "workbench hidden rule", "workbench public payoff"],
                        "non_reusable_content": ["source character names", "source system names"],
                        "structure_confidence": "high",
                        "analysis_basis": "cleaned_transcript",
                        "evidence": {
                            "opening_5s_hook": {
                                "segment_indexes": [1],
                                "excerpts": ["Source opens with everyone misunderstanding the hero in public."],
                            },
                            "first_payoff": {
                                "segment_indexes": [3],
                                "excerpts": ["The hidden rule pays off when the crowd sees the result."],
                            },
                        },
                    },
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "direction": "Turn into a campus story.",
            "output_type": "short_fiction",
            "similarity_level": "medium",
            "target_length": "3000 Chinese characters",
            "keep_narration": True,
        },
    )

    assert response.status_code == 200
    project = response.json()["project"]
    assert project["story_workbench_source"] == "saved_story_workbench"
    assert project["story_workbench_analysis"]["opening_5s_hook"] == "Hero is publicly misunderstood."
    assert project["story_workbench_analysis"]["reusable_template"][0] == "workbench low opening"
    assert project["structure_template"] == ["workbench low opening", "workbench hidden rule", "workbench public payoff"]
    assert "source system names" in project["anti_copy_rules"]
    assert "## 故事工坊拆解" in project["reference_markdown"]
    assert "Hidden rule appears quickly." in project["reference_markdown"]
    assert "source character names" in project["reference_markdown"]
    assert "### 结构节点证据与创作边界" in project["reference_markdown"]
    assert "Source opens with everyone misunderstanding the hero in public." in project["reference_markdown"]
    assert "原文证据片段（不可直接复用，段落 1）" in project["reference_markdown"]
    assert "只保留结构功能，必须更换人物、场景、事件载体和具体表达" in project["reference_markdown"]


def test_imitation_factory_checks_generated_draft_copy_risk(tmp_path, monkeypatch):
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
                    "video_title": "High copy source",
                    "summary": "summary",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "hook",
                        "opening_hook": "opening",
                        "structure": ["Humiliation", "Hidden trigger", "Reward"],
                        "emotional_curve": [],
                    },
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "story_workbench_items": [
                {
                    "report_id": "report-1",
                    "cleaned_text": "鎵€鏈変汉閮界灖涓嶈捣杩欎釜瀹炰範鐢熴€俓n鐩村埌浠栬Е鍙戦殣钘忕郴缁熷鍔便€俓n鍏ㄥ満閮芥矇榛樹簡銆?",
                    "segments": [],
                    "analysis": {},
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())
    project = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "direction": "鎹㈡垚閮藉競鑱屽満鐭墖灏忚銆?",
            "output_type": "short_fiction",
            "similarity_level": "medium",
            "target_length": "3000 Chinese characters",
            "keep_narration": True,
        },
    ).json()["project"]

    response = client.post(
        f"/api/imitation-factory/projects/{project['id']}/drafts",
        json={
            "title": "High overlap draft",
            "draft_text": "鎵€鏈変汉閮界灖涓嶈捣杩欎釜瀹炰範鐢熴€傜洿鍒颁粬瑙﹀彂闅愯棌绯荤粺濂栧姳銆傞殢鍚庡叏鍦洪兘娌夐粯浜嗐€?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    report = body["draft"]["similarity_report"]
    assert body["project"]["generated_drafts"][0]["title"] == "High overlap draft"
    assert body["project"]["latest_similarity_report"]["risk_level"] == "high"
    assert body["draft"]["status"] == "needs_revision"
    assert report["text_overlap_percent"] >= 18
    assert report["plot_similarity"] >= 0.5
    assert report["pacing_similarity"] >= 0.5
    assert report["repeated_phrases"]
    assert report["risk_segments"]
    assert report["risk_segments"][0]["risk_type"] == "text_overlap"
    assert report["risk_segments"][0]["action_level"] == "must_fix"
    assert report["risk_segments"][0]["action_label"]
    assert report["risk_segments"][0]["draft_excerpt"]
    assert report["quality_gate"]["status"] == "blocked"
    assert "text_overlap" in report["quality_gate"]["failed_checks"]
    assert report["recommendations"]


def test_imitation_factory_detects_plot_and_pacing_similarity(tmp_path, monkeypatch):
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
                    "video_title": "Plot order source",
                    "summary": "summary",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "hook",
                        "opening_hook": "opening",
                        "structure": ["Pressure", "Hidden trigger", "Payoff", "Public reversal"],
                        "emotional_curve": [],
                    },
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "story_workbench_items": [
                {
                    "report_id": "report-1",
                    "cleaned_text": "浼椾汉鍏紑璐ㄧ枒閭ｄ釜鏂颁汉銆俓n濂瑰彂鐜颁竴涓殣钘忚鍒欍€俓n澶囩敤鐏粰鍑虹涓€浠藉鍔便€俓n鍏ㄥ満褰撲紬娌夐粯鍙嶈浆銆?",
                    "segments": [],
                    "analysis": {},
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())
    project = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "direction": "鎹㈡垚鏈潵缁翠慨绔欐晠浜嬨€?",
            "output_type": "short_fiction",
            "similarity_level": "medium",
            "target_length": "2500 Chinese characters",
            "keep_narration": True,
        },
    ).json()["project"]

    response = client.post(
        f"/api/imitation-factory/projects/{project['id']}/drafts",
        json={
            "title": "Same plot order",
            "draft_text": "浜虹兢浣庝及骞磋交缁翠慨甯堛€俓n濂瑰惎鍔ㄤ竴鏉￠殣钘忓崗璁€俓n鏍稿績浜曚寒璧风涓€閬撳洖鍝嶃€俓n鍥磋鑰呭叕寮€鎰忚瘑鍒板垽鏂敊浜嗐€?",
        },
    )

    assert response.status_code == 200
    report = response.json()["draft"]["similarity_report"]
    assert report["text_overlap_percent"] < 18
    assert report["plot_similarity"] >= 0.9
    assert report["pacing_similarity"] >= 0.9
    assert report["risk_level"] == "medium"
    assert any(segment["risk_type"] in {"plot_order", "pacing"} for segment in report["risk_segments"])
    assert {segment["action_level"] for segment in report["risk_segments"]} == {"should_fix"}
    assert all(segment["action_label"] for segment in report["risk_segments"])
    assert report["recommendations"]


def test_imitation_factory_detects_semantic_plot_similarity(tmp_path, monkeypatch):
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
                    "video_title": "Semantic source",
                    "summary": "summary",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "hook",
                        "opening_hook": "opening",
                        "structure": ["Pressure", "Hidden trigger", "Evidence", "Public reversal"],
                        "emotional_curve": [],
                    },
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "story_workbench_items": [
                    {
                        "report_id": "report-1",
                        "cleaned_text": (
                            "A lowly intern is pressured by everyone in the meeting.\n"
                            "A hidden system rule appears after she notices the contract log.\n"
                            "The evidence proves the rival changed the record.\n"
                            "The public reversal leaves the room silent."
                        ),
                    "segments": [],
                    "analysis": {},
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())
    project = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "direction": "Create a new workplace story.",
            "output_type": "short_fiction",
            "similarity_level": "medium",
            "target_length": "2500 Chinese characters",
            "keep_narration": False,
        },
    ).json()["project"]

    response = client.post(
        f"/api/imitation-factory/projects/{project['id']}/drafts",
        json={
            "title": "Semantic same beats",
            "draft_text": (
                "The overlooked trainee faces public pressure from the gathered staff.\n"
                "A secret protocol activates when she inspects the signed file.\n"
                "The proof shows her opponent falsified the archive.\n"
                "The truth creates a reversal and the audience goes quiet."
            ),
        },
    )

    assert response.status_code == 200
    report = response.json()["draft"]["similarity_report"]
    assert report["semantic_similarity"] >= 0.82
    assert report["text_overlap_percent"] < 18
    assert report["risk_level"] == "medium"
    assert report["quality_gate"]["status"] == "needs_revision"
    assert "semantic_similarity" in report["quality_gate"]["failed_checks"]
    assert any(segment["risk_type"] == "semantic_plot" for segment in report["risk_segments"])
    semantic_segment = next(segment for segment in report["risk_segments"] if segment["risk_type"] == "semantic_plot")
    assert semantic_segment["similarity_reason"]
    assert semantic_segment["suggested_rewrite_mode"] == "plot_reframe"
    assert "事件载体" in semantic_segment["rewrite_goal"]
    assert "事件载体" in semantic_segment["must_replace"]
    assert semantic_segment["can_keep"]
    assert any("语义桥段" in item for item in report["recommendations"])


def test_imitation_factory_allows_low_overlap_generated_draft(tmp_path, monkeypatch):
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
                    "video_title": "Low copy source",
                    "summary": "summary",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "hook",
                        "opening_hook": "opening",
                        "structure": ["Public pressure", "First payoff"],
                        "emotional_curve": [],
                    },
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "story_workbench_items": [
                {
                    "report_id": "report-1",
                    "cleaned_text": "lowly apprentice waits\nancient copper wakes\nelder admits mistake",
                    "segments": [],
                    "analysis": {},
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())
    project = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "direction": "鎹㈡垚鏈潵鍩庡競閲岀殑缁翠慨甯堟晠浜嬨€?",
            "output_type": "short_fiction",
            "similarity_level": "low",
            "target_length": "3000 Chinese characters",
            "keep_narration": False,
        },
    ).json()["project"]

    response = client.post(
        f"/api/imitation-factory/projects/{project['id']}/drafts",
        json={
            "title": "Low overlap draft",
            "draft_text": "闆ㄥ鐨勮建閬撶珯绐佺劧鏂數锛屽勾杞荤淮淇笀鐙嚜杩涘叆鏍稿績浜曘€傚ス娌℃湁瑙ｉ噴杩囧幓锛屽彧鍏堣澶囩敤鐏竴鐩忕洀浜捣銆傚洿瑙傝€呮剰璇嗗埌鐪熸鐨勫嵄鏈轰笉鏄仠鐢碉紝鑰屾槸鍩庡競涓灑琚汉璋冨寘銆?",
        },
    )

    assert response.status_code == 200
    body = response.json()
    report = body["draft"]["similarity_report"]
    assert report["risk_level"] == "low"
    assert body["draft"]["status"] == "publishable"
    assert report["quality_gate"]["status"] == "pass"
    assert report["text_overlap_percent"] < 8
    assert report["repeated_phrases"] == []


def test_imitation_factory_quality_gate_passes_publishable_draft(tmp_path, monkeypatch):
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
                    "video_title": "Publishable source",
                    "summary": "summary",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "hook",
                        "opening_hook": "opening",
                        "structure": ["Pressure", "Trigger", "Payoff"],
                        "emotional_curve": [],
                    },
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "story_workbench_items": [
                {
                    "report_id": "report-1",
                    "cleaned_text": "鏉戝彛鐨勪汉閮借浠栨病鍑烘伅銆俓n涓€鏋氭棫閾滈挶璁╃绁犱寒璧枫€俓n鏃忛暱缁堜簬鎵胯鑷繁鐪嬮敊浜嗐€?",
                    "segments": [],
                    "analysis": {},
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())
    project = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "direction": "鎹㈡垚鏈潵鍩庡競閲岀殑缁翠慨甯堟晠浜嬨€?",
            "output_type": "short_fiction",
            "similarity_level": "low",
            "target_length": "3000 Chinese characters",
            "keep_narration": False,
        },
    ).json()["project"]

    response = client.post(
        f"/api/imitation-factory/projects/{project['id']}/drafts",
        json={
            "title": "Publishable draft",
            "draft_text": "quiet mechanic stands\nremote beacon answers\ncaptain accepts failure",
        },
    )

    report = response.json()["draft"]["similarity_report"]

    assert response.status_code == 200
    assert report["quality_gate"]["status"] == "pass"
    assert report["quality_gate"]["passed"] is True
    assert report["quality_gate"]["failed_checks"] == []
    assert response.json()["draft"]["status"] == "publishable"


def test_imitation_factory_blocks_publishable_status_for_failed_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [],
            "imitation_projects": [
                {
                    "id": "imitate-1",
                    "name": "Blocked draft",
                    "source_video_title": "Source story",
                    "direction": "New setting",
                    "output_type": "short_fiction",
                    "reference_markdown": "Reference package",
                    "generated_drafts": [
                        {
                            "id": "draft-1",
                            "title": "Blocked",
                            "status": "needs_revision",
                            "draft_text": "Draft body",
                            "similarity_report": {
                                "risk_level": "high",
                                "text_overlap_percent": 24.0,
                                "quality_gate": {
                                    "status": "blocked",
                                    "failed_checks": ["text_overlap"],
                                    "passed": False,
                                    "failed_checks": ["text_overlap"],
                                },
                            },
                        }
                    ],
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    marked = client.patch(
        "/api/imitation-factory/projects/imitate-1/drafts/draft-1",
        json={"status": "publishable"},
    )
    project = client.get("/api/imitation-factory").json()["projects"][0]

    assert marked.status_code == 422
    assert marked.json()["detail"] == "high_risk"
    assert project["generated_drafts"][0]["status"] == "needs_revision"


def test_imitation_factory_detects_reused_story_entities(tmp_path, monkeypatch):
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
                    "video_title": "Entity source",
                    "summary": "summary",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "hook",
                        "opening_hook": "opening",
                        "structure": ["Fall", "Token", "Return"],
                        "emotional_curve": [],
                    },
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "story_workbench_items": [
                {
                    "report_id": "report-1",
                    "cleaned_text": "Lin Beichen was expelled from Qingyun City after finding the Tianji Token. The Tianji Token opened the Xinghe System.",
                    "segments": [],
                    "analysis": {},
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())
    project = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "direction": "鎹㈡垚鐜颁唬鎮枒鏁呬簨銆?",
            "output_type": "short_fiction",
            "similarity_level": "low",
            "target_length": "3000 Chinese characters",
            "keep_narration": False,
        },
    ).json()["project"]

    response = client.post(
        f"/api/imitation-factory/projects/{project['id']}/drafts",
        json={
            "title": "Entity reuse draft",
            "draft_text": "Years later in Qingyun City, another heir fought for the Tianji Token while the Xinghe System waited.",
        },
    )

    assert response.status_code == 200
    report = response.json()["draft"]["similarity_report"]
    assert report["reused_entities"]
    assert any("Qingyun" in entity or "Tianji" in entity for entity in report["reused_entities"])
    assert report["risk_level"] == "high"
    assert any(segment["risk_type"] == "entity_reuse" for segment in report["risk_segments"])
    assert report["recommendations"]


def test_imitation_factory_runs_inkos_and_saves_returned_draft(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    monkeypatch.setenv("YCA_INKOS_PROJECT_DIR", str(tmp_path / "inkos-runs"))
    fake_inkos = tmp_path / "fake_inkos.py"
    fake_inkos.write_text(
        """
import json
import pathlib
import sys

args = sys.argv[1:]
out_dir = pathlib.Path(args[args.index("--out-dir") + 1])
story_id = args[args.index("--story-id") + 1]
final = out_dir / story_id / "final" / "full.md"
final.parent.mkdir(parents=True, exist_ok=True)
final.write_text("# Generated story\\nThe repair worker lights the city core.", encoding="utf-8")
print(json.dumps({"storyId": story_id, "finalMarkdownPath": str(final)}, ensure_ascii=False))
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("YCA_INKOS_COMMAND", f'"{sys.executable}" "{fake_inkos}"')
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
                    "video_title": "InkOS source",
                    "summary": "summary",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "hook",
                        "opening_hook": "opening",
                        "structure": ["Pressure", "Payoff"],
                        "emotional_curve": [],
                    },
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "story_workbench_items": [
                {
                    "report_id": "report-1",
                    "cleaned_text": "鎵€鏈変汉閮界灖涓嶈捣杩欎釜瀹炰範鐢熴€傜洿鍒颁粬瑙﹀彂闅愯棌绯荤粺濂栧姳銆?",
                    "segments": [],
                    "analysis": {},
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())
    project = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "direction": "鎹㈡垚鏈潵鍩庡競缁翠慨甯堢煭鐗囧皬璇淬€?",
            "output_type": "short_fiction",
            "similarity_level": "medium",
            "target_length": "3000 Chinese characters",
            "keep_narration": True,
        },
    ).json()["project"]

    response = client.post(f"/api/imitation-factory/projects/{project['id']}/inkos/run")

    assert response.status_code == 200
    body = response.json()
    draft = body["draft"]
    assert draft["source"] == "inkos"
    assert "The repair worker lights the city core." in draft["draft_text"]
    assert draft["similarity_report"]["risk_level"] == "low"
    assert body["project"]["generated_drafts"][0]["id"] == draft["id"]
    last_run = body["project"]["last_inkos_run"]
    assert last_run["id"].startswith("inkos-run-")
    assert last_run["status"] == "complete"
    assert last_run["elapsed_ms"] >= 0
    assert last_run["request"]["direction"]
    assert last_run["request"]["reference_length"] > 0
    assert last_run["request"]["generation_preview"]["reference_length"] == last_run["request"]["reference_length"]
    assert last_run["request"]["generation_preview"]["estimated_total_tokens"] > 0
    assert last_run["draft_preview"]
    assert body["project"]["inkos_run_history"][0]["id"] == last_run["id"]
    assert draft["inkos_result"]["run_id"] == last_run["id"]
    assert draft["inkos_result"]["request"]["reference_length"] == last_run["request"]["reference_length"]


def test_project_library_bulk_runs_inkos_for_selected_projects(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    monkeypatch.setenv("YCA_INKOS_PROJECT_DIR", str(tmp_path / "inkos-runs"))
    fake_inkos = tmp_path / "fake_inkos_bulk.py"
    fake_inkos.write_text(
        """
import json
import pathlib
import sys

args = sys.argv[1:]
out_dir = pathlib.Path(args[args.index("--out-dir") + 1])
story_id = args[args.index("--story-id") + 1]
final = out_dir / story_id / "final" / "full.md"
final.parent.mkdir(parents=True, exist_ok=True)
final.write_text("A new original draft moves the reveal to a night school hearing.", encoding="utf-8")
print(json.dumps({"storyId": story_id, "finalMarkdownPath": str(final)}, ensure_ascii=False))
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("YCA_INKOS_COMMAND", f'"{sys.executable}" "{fake_inkos}"')
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [],
            "story_workbench_items": [],
            "imitation_projects": [
                {
                    "id": "project-ready",
                    "name": "Ready reference",
                    "direction": "New setting",
                    "output_type": "short_fiction",
                    "similarity_level": "medium",
                    "reference_markdown": "Reference package",
                    "source_script_excerpt": "Original source text.",
                    "generated_drafts": [],
                    "created_at": "2026-06-09T12:00:00+00:00",
                },
                {
                    "id": "project-publishable",
                    "name": "Already publishable",
                    "reference_markdown": "Reference package",
                    "generated_drafts": [{"id": "draft-ok", "status": "publishable"}],
                },
                {
                    "id": "project-no-reference",
                    "name": "No reference",
                    "reference_markdown": "",
                    "generated_drafts": [],
                },
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/projects/bulk-inkos",
        json={"project_ids": ["project-ready", "project-publishable", "project-no-reference", "missing"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["generated_count"] == 1
    assert body["generated"][0]["project_id"] == "project-ready"
    assert body["generated"][0]["draft_id"]
    assert body["skipped_count"] == 3
    assert {item["reason"] for item in body["skipped"]} == {"already_publishable", "no_reference_package", "not_found"}
    ready = next(project for project in body["projects"] if project["id"] == "project-ready")
    assert ready["generated_drafts"][0]["source"] == "inkos"


def test_imitation_factory_reruns_inkos_with_historical_reference_package(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    monkeypatch.setenv("YCA_INKOS_PROJECT_DIR", str(tmp_path / "inkos-runs"))
    fake_inkos = tmp_path / "fake_inkos_reference.py"
    fake_inkos.write_text(
        """
import json
import pathlib
import sys

args = sys.argv[1:]
out_dir = pathlib.Path(args[args.index("--out-dir") + 1])
story_id = args[args.index("--story-id") + 1]
reference_path = pathlib.Path(args[args.index("--reference") + 1])
reference_text = reference_path.read_text(encoding="utf-8")
final = out_dir / story_id / "final" / "full.md"
final.parent.mkdir(parents=True, exist_ok=True)
final.write_text(reference_text, encoding="utf-8")
print(json.dumps({"storyId": story_id, "finalMarkdownPath": str(final)}, ensure_ascii=False))
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("YCA_INKOS_COMMAND", f'"{sys.executable}" "{fake_inkos}"')
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [],
            "sample_analyses": [],
            "jobs": [],
            "imitation_projects": [
                {
                    "id": "project-1",
                    "name": "Historical reference project",
                    "source_report_id": "report-1",
                    "source_video_title": "Source",
                    "source_video_url": "https://www.youtube.com/watch?v=source",
                    "direction": "Direction",
                    "output_type": "short_fiction",
                    "similarity_level": "low",
                    "target_length": "1000 characters",
                    "keep_narration": False,
                    "reference_markdown": "CURRENT_REFERENCE_SHOULD_NOT_BE_USED",
                    "inkos_preview": {"reference_length": 36, "estimated_total_tokens": 10},
                    "generated_drafts": [],
                    "inkos_run_history": [
                        {
                            "id": "inkos-run-old",
                            "status": "complete",
                            "request": {
                                "reference_length": 31,
                                "reference_markdown": "HISTORICAL_REFERENCE_SHOULD_BE_USED",
                            },
                            "ran_at": "2026-06-09T12:00:00+00:00",
                        }
                    ],
                }
            ],
        },
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/imitation-factory/projects/project-1/inkos/run",
        json={"reference_run_id": "inkos-run-old"},
    )

    assert response.status_code == 200
    body = response.json()
    draft = body["draft"]
    last_run = body["project"]["last_inkos_run"]
    assert "HISTORICAL_REFERENCE_SHOULD_BE_USED" in draft["draft_text"]
    assert "CURRENT_REFERENCE_SHOULD_NOT_BE_USED" not in draft["draft_text"]
    assert last_run["request"]["reference_run_id"] == "inkos-run-old"
    assert last_run["request"]["reference_markdown"] == "HISTORICAL_REFERENCE_SHOULD_BE_USED"
    assert body["project"]["inkos_run_history"][0]["id"] == last_run["id"]


def test_imitation_factory_records_inkos_run_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_INKOS_COMMAND", "missing-inkos-command")
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
                    "video_title": "InkOS missing",
                    "summary": "summary",
                    "creative_breakdown": {"structure": [], "emotional_curve": []},
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "story_workbench_items": [
                {
                    "report_id": "report-1",
                    "cleaned_text": "娓呮礂鍚庣殑鍙傝€冩枃妗堛€?",
                    "segments": [],
                    "analysis": {},
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())
    project = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "direction": "鎹㈡垚鏍″洯鏁呬簨銆?",
            "output_type": "short_fiction",
            "similarity_level": "medium",
            "target_length": "3000 Chinese characters",
            "keep_narration": True,
        },
    ).json()["project"]

    response = client.post(f"/api/imitation-factory/projects/{project['id']}/inkos/run")
    listed = client.get("/api/imitation-factory").json()["projects"][0]

    assert response.status_code == 502
    response_detail = response.json()["detail"]
    assert response_detail["message"] == "InkOS command was not found. Install InkOS or set YCA_INKOS_COMMAND."
    assert response_detail["project"]["id"] == project["id"]
    assert response_detail["project"]["last_inkos_run"]["status"] == "failed"
    assert listed["inkos_status"] == "inkos_failed"
    assert listed["last_inkos_run"]["status"] == "failed"
    assert listed["last_inkos_run"]["id"].startswith("inkos-run-")
    assert listed["last_inkos_run"]["elapsed_ms"] >= 0
    assert listed["last_inkos_run"]["request"]["direction"]
    assert response_detail["project"]["last_inkos_run"]["request"]["direction"] == listed["last_inkos_run"]["request"]["direction"]
    assert listed["last_inkos_run"]["error_message"]
    assert listed["inkos_run_history"][0]["id"] == listed["last_inkos_run"]["id"]


def test_imitation_factory_exports_marks_and_reduces_draft_risk(tmp_path, monkeypatch):
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
                    "video_title": "Risk rewrite source",
                    "summary": "summary",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "hook",
                        "opening_hook": "opening",
                        "structure": ["Humiliation", "Hidden trigger", "Reward"],
                        "emotional_curve": [],
                    },
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "story_workbench_items": [
                {
                    "report_id": "report-1",
                    "cleaned_text": "鎵€鏈変汉閮界灖涓嶈捣杩欎釜瀹炰範鐢熴€俓n鐩村埌浠栬Е鍙戦殣钘忕郴缁熷鍔便€俓n鍏ㄥ満閮芥矇榛樹簡銆?",
                    "segments": [],
                    "analysis": {},
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())
    project = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "direction": "鎹㈡垚閮藉競鑱屽満鐭墖灏忚銆?",
            "output_type": "short_fiction",
            "similarity_level": "medium",
            "target_length": "3000 Chinese characters",
            "keep_narration": True,
        },
    ).json()["project"]
    saved = client.post(
        f"/api/imitation-factory/projects/{project['id']}/drafts",
        json={
            "title": "Needs rewrite",
            "draft_text": "鎵€鏈変汉閮界灖涓嶈捣杩欎釜瀹炰範鐢熴€傜洿鍒颁粬瑙﹀彂闅愯棌绯荤粺濂栧姳銆傚叏鍦洪兘娌夐粯浜嗐€?",
        },
    ).json()["draft"]

    exported = client.get(f"/api/imitation-factory/projects/{project['id']}/drafts/{saved['id']}/markdown")
    marked = client.patch(
        f"/api/imitation-factory/projects/{project['id']}/drafts/{saved['id']}",
        json={"status": "needs_revision"},
    )
    reduced = client.post(f"/api/imitation-factory/projects/{project['id']}/drafts/{saved['id']}/reduce-risk")

    assert exported.status_code == 200
    assert exported.json()["filename"] == "needs-rewrite.md"
    export_markdown = exported.json()["markdown"]
    assert "# Needs rewrite" in export_markdown
    assert "## 质量与风险摘要" in export_markdown
    assert "- Quality gate:" in export_markdown
    assert "- Text overlap:" in export_markdown
    assert "- Semantic plot similarity:" in export_markdown
    assert "## 发布前检查" in export_markdown
    assert "## 正文" in export_markdown
    assert saved["draft_text"] in export_markdown
    assert marked.status_code == 200
    assert marked.json()["draft"]["status"] == "needs_revision"
    assert reduced.status_code == 200
    new_draft = reduced.json()["draft"]
    assert new_draft["id"] != saved["id"]
    assert new_draft["inkos_result"]["parent_draft_id"] == saved["id"]
    comparison = new_draft["inkos_result"]["rewrite_comparison"]
    assert comparison["mode"] == "reduce_risk"
    assert comparison["before"]["risk_level"] == saved["similarity_report"]["risk_level"]
    assert comparison["after"]["risk_level"] == new_draft["similarity_report"]["risk_level"]
    assert comparison["delta"]["text_overlap_percent"] < 0
    assert new_draft["similarity_report"]["text_overlap_percent"] < saved["similarity_report"]["text_overlap_percent"]
    history = reduced.json()["project"]["similarity_report_history"]
    assert len(history) == 2
    assert history[0]["draft_id"] == new_draft["id"]
    assert history[1]["draft_id"] == saved["id"]
    assert history[0]["risk_level"] == new_draft["similarity_report"]["risk_level"]


def test_imitation_factory_rewrites_draft_with_mode(tmp_path, monkeypatch):
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
                    "video_title": "Rewrite source",
                    "summary": "summary",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "hook",
                        "opening_hook": "opening",
                        "structure": ["Conflict", "Payoff"],
                        "emotional_curve": [],
                    },
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "story_workbench_items": [
                {
                    "report_id": "report-1",
                    "cleaned_text": "鏃ф晠浜嬬涓€鍙ャ€俓n鏃ф晠浜嬬浜屽彞銆?",
                    "segments": [],
                    "analysis": {},
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())
    project = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "direction": "鎹㈡垚鐭墽鍐茬獊銆?",
            "output_type": "short_drama",
            "similarity_level": "low",
            "target_length": "1200 Chinese characters",
            "keep_narration": False,
        },
    ).json()["project"]
    saved = client.post(
        f"/api/imitation-factory/projects/{project['id']}/drafts",
        json={
            "title": "Base draft",
            "draft_text": "濂冲琚綋浼楄川鐤戙€傚ス鎷垮嚭璇佹嵁銆傚鎵嬫矇榛樸€?",
        },
    ).json()["draft"]

    response = client.post(
        f"/api/imitation-factory/projects/{project['id']}/drafts/{saved['id']}/rewrite",
        json={"mode": "short_drama"},
    )

    assert response.status_code == 200
    body = response.json()
    rewritten = body["draft"]
    assert rewritten["id"] != saved["id"]
    assert rewritten["inkos_result"]["parent_draft_id"] == saved["id"]
    assert rewritten["inkos_result"]["rewrite_strategy"] == "short_drama"
    comparison = rewritten["inkos_result"]["rewrite_comparison"]
    assert comparison["mode"] == "short_drama"
    assert comparison["parent_draft_id"] == saved["id"]
    assert comparison["before"]["risk_level"] == saved["similarity_report"]["risk_level"]
    assert comparison["after"]["risk_level"] == rewritten["similarity_report"]["risk_level"]
    assert "短剧对白版" in rewritten["title"]
    assert rewritten["draft_text"]
    assert body["project"]["generated_drafts"][0]["id"] == rewritten["id"]


def test_imitation_factory_rewrites_draft_with_compressed_mode(tmp_path, monkeypatch):
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
                    "video_title": "Compressed rewrite source",
                    "summary": "summary",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "hook",
                        "opening_hook": "opening",
                        "structure": ["Conflict", "Payoff"],
                        "emotional_curve": [],
                    },
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "story_workbench_items": [
                {
                    "report_id": "report-1",
                    "cleaned_text": "Source sentence one.\nSource sentence two.",
                    "segments": [],
                    "analysis": {},
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())
    project = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "direction": "Create a shorter story draft.",
            "output_type": "short_fiction",
            "similarity_level": "low",
            "target_length": "800 Chinese characters",
            "keep_narration": False,
        },
    ).json()["project"]
    long_draft = "\n".join(
        [
            "The intern enters the meeting with no one taking her seriously",
            "Her manager repeats the accusation in front of everyone",
            "She stays quiet because the real evidence is still uploading",
            "The rival smiles because he thinks the trap has already worked",
            "A notification appears on the screen behind the executive",
            "The contract log proves the rival changed the numbers",
            "The room falls silent as the truth becomes impossible to deny",
            "The intern finally speaks and asks for the audit to continue",
            "The executive realizes the quietest person saw everything",
            "The rival loses control of the story he tried to write",
        ]
    )
    saved = client.post(
        f"/api/imitation-factory/projects/{project['id']}/drafts",
        json={"title": "Long base draft", "draft_text": long_draft},
    ).json()["draft"]

    response = client.post(
        f"/api/imitation-factory/projects/{project['id']}/drafts/{saved['id']}/rewrite",
        json={"mode": "compressed"},
    )

    assert response.status_code == 200
    body = response.json()
    rewritten = body["draft"]
    assert rewritten["id"] != saved["id"]
    assert rewritten["source"] == "rewrite_compressed"
    assert rewritten["inkos_result"]["rewrite_strategy"] == "compressed"
    assert rewritten["inkos_result"]["rewrite_comparison"]["mode"] == "compressed"
    assert len(rewritten["draft_text"]) < len(saved["draft_text"])
    assert body["project"]["generated_drafts"][0]["id"] == rewritten["id"]


def test_imitation_factory_rewrites_draft_with_plot_reframe_mode(tmp_path, monkeypatch):
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
                    "video_title": "Plot reframe source",
                    "summary": "summary",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "hook",
                        "opening_hook": "opening",
                        "structure": ["Pressure", "Hidden trigger", "Evidence", "Public reversal"],
                        "emotional_curve": [],
                    },
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "story_workbench_items": [
                {
                    "report_id": "report-1",
                    "cleaned_text": (
                        "A lowly intern is pressured by everyone in the meeting.\n"
                        "A hidden system rule appears after she notices the contract log.\n"
                        "The evidence proves the rival changed the record.\n"
                        "The public reversal leaves the room silent."
                    ),
                    "segments": [],
                    "analysis": {},
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())
    project = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "direction": "Create a new workplace story.",
            "output_type": "short_fiction",
            "similarity_level": "medium",
            "target_length": "2500 Chinese characters",
            "keep_narration": False,
        },
    ).json()["project"]
    saved = client.post(
        f"/api/imitation-factory/projects/{project['id']}/drafts",
        json={
            "title": "Semantic same beats",
            "draft_text": (
                "The overlooked trainee faces public pressure from the gathered staff.\n"
                "A secret protocol activates when she inspects the signed file.\n"
                "The proof shows her opponent falsified the archive.\n"
                "The truth creates a reversal and the audience goes quiet."
            ),
        },
    ).json()["draft"]

    assert saved["similarity_report"]["semantic_similarity"] >= 0.82
    response = client.post(
        f"/api/imitation-factory/projects/{project['id']}/drafts/{saved['id']}/rewrite",
        json={"mode": "plot_reframe"},
    )

    assert response.status_code == 200
    body = response.json()
    rewritten = body["draft"]
    comparison = rewritten["inkos_result"]["rewrite_comparison"]
    assert rewritten["id"] != saved["id"]
    assert rewritten["source"] == "rewrite_plot_reframe"
    assert rewritten["inkos_result"]["rewrite_strategy"] == "plot_reframe"
    assert comparison["mode"] == "plot_reframe"
    assert comparison["before"]["semantic_similarity"] == saved["similarity_report"]["semantic_similarity"]
    assert "semantic_similarity" in comparison["after"]
    assert "semantic_similarity" in comparison["delta"]
    assert rewritten["draft_text"] != saved["draft_text"]
    assert body["project"]["generated_drafts"][0]["id"] == rewritten["id"]


def test_imitation_factory_rewrites_selected_risk_segment(tmp_path, monkeypatch):
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
                    "video_title": "Segment risk source",
                    "summary": "summary",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "hook",
                        "opening_hook": "opening",
                        "structure": ["Public pressure", "Hidden trigger", "Payoff"],
                        "emotional_curve": ["Pressure", "Payoff"],
                    },
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "comment_insights": {"status": "not_configured"},
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "story_workbench_items": [
                {
                    "report_id": "report-1",
                    "cleaned_text": "鎵€鏈変汉閮界灖涓嶈捣杩欎釜瀹炰範鐢熴€俓n鐩村埌浠栬Е鍙戦殣钘忕郴缁熷鍔便€俓n鍏ㄥ満閮芥矇榛樹簡銆?",
                    "segments": [],
                    "analysis": {},
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())
    project = client.post(
        "/api/imitation-factory/projects",
        json={
            "report_id": "report-1",
            "direction": "鎹㈡垚鏈潵缁翠慨绔欐晠浜嬨€?",
            "output_type": "short_fiction",
            "similarity_level": "medium",
            "target_length": "2500 Chinese characters",
            "keep_narration": True,
        },
    ).json()["project"]
    saved = client.post(
        f"/api/imitation-factory/projects/{project['id']}/drafts",
        json={
            "title": "Segment risk",
            "draft_text": "鎵€鏈変汉閮界灖涓嶈捣杩欎釜瀹炰範鐢熴€傜洿鍒颁粬瑙﹀彂闅愯棌绯荤粺濂栧姳銆傚叏鍦洪兘娌夐粯浜嗐€?",
        },
    ).json()["draft"]

    assert saved["similarity_report"]["risk_segments"]
    response = client.post(
        f"/api/imitation-factory/projects/{project['id']}/drafts/{saved['id']}/rewrite-risk-segment",
        json={"segment_index": 0},
    )

    assert response.status_code == 200
    body = response.json()
    rewritten = body["draft"]
    assert rewritten["id"] != saved["id"]
    assert rewritten["source"] == "risk_segment_rewrite"
    assert rewritten["inkos_result"]["parent_draft_id"] == saved["id"]
    assert rewritten["inkos_result"]["risk_segment_index"] == 0
    comparison = rewritten["inkos_result"]["rewrite_comparison"]
    assert comparison["mode"] == "risk_segment"
    assert comparison["parent_draft_id"] == saved["id"]
    assert comparison["before"]["risk_segment_count"] >= comparison["after"]["risk_segment_count"]
    assert rewritten["draft_text"] != saved["draft_text"]
    assert body["project"]["generated_drafts"][0]["id"] == rewritten["id"]
    assert body["project"]["similarity_report_history"][0]["draft_id"] == rewritten["id"]


def test_dashboard_includes_creation_pipeline_project_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    recent_at = datetime.now(UTC).isoformat()
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [
                {
                    "id": "video-1",
                    "title": "Source 1",
                    "url": "https://www.youtube.com/watch?v=one",
                    "analysis_status": "complete",
                },
                {
                    "id": "video-2",
                    "title": "Source 2",
                    "url": "https://www.youtube.com/watch?v=two",
                    "analysis_status": "pending",
                },
                {
                    "id": "video-3",
                    "title": "Source 3",
                    "url": "https://www.youtube.com/watch?v=three",
                    "analysis_status": "pending",
                },
                {
                    "id": "video-4",
                    "title": "Source 4",
                    "url": "https://www.youtube.com/watch?v=four",
                    "analysis_status": "pending",
                },
            ],
            "idea_cards": [],
            "reports": [
                {
                    "id": "report-1",
                    "video_url": "https://www.youtube.com/watch?v=one",
                    "created_at": recent_at,
                }
            ],
            "story_workbench_items": [
                {
                    "report_id": "report-1",
                    "cleaned_text": "Cleaned story text.",
                    "analysis": {
                        "opening_5s_hook": "Open with public pressure.",
                        "first_payoff": "Hidden rule pays off.",
                    },
                }
            ],
            "imitation_projects": [
                {
                    "id": "imitate-1",
                    "name": "Project 1",
                    "source_video_title": "Source 1",
                    "source_video_url": "https://www.youtube.com/watch?v=one",
                    "source_channel_title": "Story Lab",
                    "source_topic_type": "story_recap",
                    "direction": "New city story",
                    "output_type": "short_fiction",
                    "similarity_level": "medium",
                    "inkos_status": "draft_checked",
                    "latest_similarity_report": {"risk_level": "high", "text_overlap_percent": 31.5},
                    "generated_drafts": [
                        {
                            "id": "draft-1",
                            "title": "Draft 1",
                            "status": "needs_revision",
                            "similarity_report": {
                                "risk_level": "high",
                                "text_overlap_percent": 31.5,
                                "quality_gate": {
                                    "status": "blocked",
                                    "failed_checks": ["text_overlap"],
                                    "summary": "鏂囨湰閲嶅悎杩囬珮",
                                },
                            },
                            "created_at": "2026-06-09T12:06:00+00:00",
                        },
                        {
                            "id": "draft-1-rewrite",
                            "title": "Draft 1 rewrite",
                            "status": "publishable",
                            "source": "risk_segment_rewrite",
                            "similarity_report": {
                                "risk_level": "low",
                                "text_overlap_percent": 3.5,
                                "quality_gate": {
                                    "status": "pass",
                                    "summary": "鍙繘鍏ヤ汉宸ョ粓瀹?",
                                },
                            },
                            "inkos_result": {
                                "parent_draft_id": "draft-1",
                                "rewrite_strategy": "risk_segment",
                            },
                            "created_at": "2026-06-09T12:08:00+00:00",
                        }
                    ],
                    "created_at": "2026-06-09T12:00:00+00:00",
                },
                {
                    "id": "imitate-2",
                    "name": "Project 2",
                    "source_video_title": "Source 2",
                    "direction": "Future repair story",
                    "output_type": "short_fiction",
                    "similarity_level": "low",
                    "inkos_status": "draft_checked",
                    "generated_drafts": [
                        {
                            "id": "draft-2",
                            "title": "Draft 2",
                            "status": "publishable",
                            "similarity_report": {
                                "risk_level": "low",
                                "text_overlap_percent": 0,
                                "quality_gate": {
                                    "status": "needs_revision",
                                    "checks": [
                                        {
                                            "key": "semantic_similarity",
                                            "label": "语义桥段",
                                            "passed": False,
                                            "value": 0.84,
                                            "target": "<= 0.82",
                                        }
                                    ],
                                    "failed_checks": ["semantic_similarity"],
                                },
                            },
                            "created_at": recent_at,
                        }
                    ],
                    "created_at": recent_at,
                },
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["reports_count"] == 1
    assert body["imitation_projects_count"] == 2
    assert body["pending_drafts_count"] == 1
    assert body["publishable_drafts_count"] == 2
    assert body["imitation_project_summaries"][0]["latest_risk_level"] == "high"
    assert body["imitation_project_summaries"][0]["draft_count"] == 2
    assert body["imitation_project_summaries"][0]["source_channel_title"] == "Story Lab"
    assert body["imitation_project_summaries"][0]["source_topic_type"] == "story_recap"
    assert body["imitation_project_summaries"][0]["latest_quality_gate_status"] == "blocked"
    assert body["imitation_project_summaries"][0]["latest_quality_gate_summary"] == "鏂囨湰閲嶅悎杩囬珮"
    assert body["imitation_project_summaries"][0]["production_priority"] == "urgent"
    assert body["imitation_project_summaries"][0]["production_priority_reason"]
    assert body["imitation_project_summaries"][0]["recommended_next_action"]
    assert body["imitation_project_summaries"][0]["updated_at"] == "2026-06-09T12:06:00+00:00"
    assert body["creation_pipeline"]["next_step"] == "quality_check"
    assert body["creation_pipeline"]["next_action"] == {
        "label": "质检并改写",
        "description": "检查文本重合、设定复用和语义桥段风险，必要时生成改写版本。",
        "target_view": "imitation-factory",
        "action_type": "open_view",
    }
    assert body["creation_pipeline"]["cleaned_story_count"] == 1
    assert body["creation_pipeline"]["structured_story_count"] == 1
    assert body["creation_pipeline"]["project_count"] == 2
    assert body["creation_pipeline"]["pending_draft_count"] == 1
    assert body["creation_quality_metrics"]["draft_count"] == 3
    assert body["creation_quality_metrics"]["quality_gate_pass_rate"] == 33.3
    assert body["creation_quality_metrics"]["average_text_overlap_percent"] == 11.7
    assert body["creation_quality_metrics"]["average_rewrite_count"] == 0.5
    assert body["creation_quality_metrics"]["high_risk_rate"] == 33.3
    assert body["creation_quality_metrics"]["failed_gate_reasons"][:2] == [
        {
            "key": "semantic_similarity",
            "label": "语义桥段",
            "count": 1,
            "draft_percent": 33.3,
            "next_action": "重构事件载体、动机和公开反转场景。",
        },
        {
            "key": "text_overlap",
            "label": "文本重合",
            "count": 1,
            "draft_percent": 33.3,
            "next_action": "先做降风险改写，降低连续表达和句式重合。",
        },
    ]
    assert body["weekly_production_metrics"]["window_days"] == 7
    assert body["weekly_production_metrics"]["analyzed_report_count"] == 1
    assert body["weekly_production_metrics"]["created_project_count"] == 1
    assert body["weekly_production_metrics"]["generated_draft_count"] == 1
    assert body["weekly_production_metrics"]["publishable_draft_count"] == 1
    assert [step["key"] for step in body["creation_funnel"]["steps"]] == [
        "synced_videos",
        "analyzed_reports",
        "creation_projects",
        "generated_drafts",
        "publishable_drafts",
    ]
    assert [step["count"] for step in body["creation_funnel"]["steps"]] == [4, 1, 2, 3, 2]
    assert [step["conversion_percent"] for step in body["creation_funnel"]["steps"]] == [100.0, 25.0, 200.0, 150.0, 66.7]
    assert body["creation_funnel"]["bottleneck"] == {
        "from": "synced_videos",
        "to": "analyzed_reports",
        "conversion_percent": 25.0,
        "summary": "候选视频进入分析报告的比例最低。",
        "next_action": "优先从候选池选择高分视频批量分析，补齐报告和字幕证据。",
    }
    pipeline_steps = {step["key"]: step for step in body["creation_pipeline"]["steps"]}
    assert set(pipeline_steps) >= {
        "settings",
        "sync",
        "analyze",
        "clean_script",
        "story_structure",
        "imitation_factory",
        "quality_check",
        "export_publish",
    }
    assert pipeline_steps["clean_script"]["count"] == 1
    assert pipeline_steps["story_structure"]["count"] == 1
    assert pipeline_steps["clean_script"]["action"] == "video-report"


def test_dashboard_next_action_guides_empty_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [],
            "story_workbench_items": [],
            "imitation_projects": [],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    pipeline = response.json()["creation_pipeline"]
    assert pipeline["next_step"] == "settings"
    assert pipeline["next_action"]["target_view"] == "settings"
    assert pipeline["next_action"]["action_type"] == "open_view"


def test_dashboard_next_action_guides_channel_sync(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [{"id": "channel-1", "url": "https://www.youtube.com/@story", "title": "Story"}],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [],
            "story_workbench_items": [],
            "imitation_projects": [],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    pipeline = response.json()["creation_pipeline"]
    assert pipeline["next_step"] == "sync"
    assert pipeline["next_action"]["action_type"] == "sync_channel"
    assert pipeline["next_action"]["target_view"] == "dashboard"


def test_dashboard_demo_workspace_loads_complete_creation_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [],
            "story_workbench_items": [],
            "imitation_projects": [],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    response = client.post("/api/dashboard/demo")
    second = client.post("/api/dashboard/demo")

    assert response.status_code == 200
    body = response.json()["dashboard"]
    assert body["channels"][0]["id"].startswith("demo-")
    assert body["reports_count"] == 1
    assert body["imitation_projects_count"] == 1
    assert body["pending_drafts_count"] == 1
    assert body["topic_candidates"]
    assert body["topic_candidates"][0]["recommendation_summary"]
    assert body["creation_pipeline"]["cleaned_story_count"] == 1
    assert body["creation_pipeline"]["structured_story_count"] == 1
    assert body["creation_quality_metrics"]["draft_count"] == 1
    assert body["favorite_structure_templates"][0]["id"].startswith("demo-")
    assert second.status_code == 200
    assert second.json()["dashboard"]["reports_count"] == 1


def test_project_library_favorites_reusable_structure_templates(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [],
            "imitation_projects": [
                {
                    "id": "imitate-1",
                    "name": "Public reversal template",
                    "source_video_title": "Source story",
                    "source_channel_title": "Story Lab",
                    "source_topic_type": "story_recap",
                    "output_type": "short_fiction",
                    "structure_template": ["Public pressure", "Hidden trigger", "Public payoff"],
                    "reuse_constraints": ["Keep mechanism"],
                    "anti_copy_rules": ["Change names"],
                    "generated_drafts": [],
                    "created_at": "2026-06-09T12:00:00+00:00",
                },
                {
                    "id": "imitate-2",
                    "name": "Template reuse success",
                    "source_template_id": "template-imitate-1",
                    "source_video_title": "Reuse story",
                    "source_channel_title": "Story Lab",
                    "source_topic_type": "story_recap",
                    "output_type": "short_fiction",
                    "generated_drafts": [
                        {
                            "id": "draft-1",
                            "status": "publishable",
                            "similarity_report": {"risk_level": "low", "text_overlap_percent": 2.0},
                        }
                    ],
                    "latest_similarity_report": {"risk_level": "low", "text_overlap_percent": 2.0},
                    "created_at": "2026-06-09T12:10:00+00:00",
                },
                {
                    "id": "imitate-3",
                    "name": "Template reuse risky",
                    "source_template_id": "template-imitate-1",
                    "source_video_title": "Reuse risky story",
                    "source_channel_title": "Story Lab",
                    "source_topic_type": "story_recap",
                    "output_type": "short_fiction",
                    "generated_drafts": [
                        {
                            "id": "draft-2",
                            "status": "needs_revision",
                            "similarity_report": {"risk_level": "high", "text_overlap_percent": 18.0},
                        }
                    ],
                    "latest_similarity_report": {"risk_level": "high", "text_overlap_percent": 18.0},
                    "created_at": "2026-06-09T12:20:00+00:00",
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    favorite = client.post("/api/projects/imitate-1/favorite-template")
    dashboard = client.get("/api/dashboard")
    unfavorite = client.delete("/api/projects/imitate-1/favorite-template")
    dashboard_after_delete = client.get("/api/dashboard")

    assert favorite.status_code == 200
    template = favorite.json()["template"]
    assert template["source_project_id"] == "imitate-1"
    assert template["structure_template"] == ["Public pressure", "Hidden trigger", "Public payoff"]
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["favorite_structure_templates"][0]["name"] == "Public reversal template"
    assert body["favorite_structure_templates"][0]["reuse_count"] == 2
    assert body["favorite_structure_templates"][0]["publishable_rate"] == 50.0
    assert body["favorite_structure_templates"][0]["average_risk_level"] == "medium"
    assert body["favorite_structure_templates"][0]["average_text_overlap_percent"] == 10.0
    assert "已复用 2 次" in body["favorite_structure_templates"][0]["recommendation_summary"]
    assert "story_recap" in body["favorite_structure_templates"][0]["recommended_usage"]
    assert body["favorite_structure_templates"][0]["tags"] == ["story_recap", "short_fiction"]
    assert body["favorite_structure_templates"][0]["applicable_topics"] == ["story_recap"]
    assert body["imitation_project_summaries"][0]["template_favorited"] is True
    assert unfavorite.status_code == 200
    assert unfavorite.json()["removed"] == 1
    assert dashboard_after_delete.json()["favorite_structure_templates"] == []
    assert dashboard_after_delete.json()["imitation_project_summaries"][0]["template_favorited"] is False


def test_project_library_updates_structure_template_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [],
            "imitation_projects": [
                {
                    "id": "imitate-1",
                    "name": "Reusable template",
                    "source_video_title": "Source story",
                    "source_channel_title": "Story Lab",
                    "source_topic_type": "revenge",
                    "output_type": "short_fiction",
                    "structure_template": ["Public pressure", "Hidden trigger", "Public payoff"],
                            "reuse_constraints": ["Keep mechanism"],
                            "anti_copy_rules": ["Change names"],
                    "generated_drafts": [],
                    "created_at": "2026-06-09T12:00:00+00:00",
                }
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())
    favorite = client.post("/api/projects/imitate-1/favorite-template").json()["template"]

    updated = client.patch(
        f"/api/projects/templates/{favorite['id']}",
        json={
            "name": "Revenge payoff engine",
            "tags": ["revenge", "payoff", "revenge"],
            "notes": "Use for public status reversal.",
            "applicable_topics": ["revenge", "system"],
            "success_cases": ["Source story publishable draft"],
        },
    )
    dashboard = client.get("/api/dashboard").json()

    assert updated.status_code == 200
    template = updated.json()["template"]
    assert template["name"] == "Revenge payoff engine"
    assert template["tags"] == ["revenge", "payoff"]
    assert template["notes"] == "Use for public status reversal."
    assert template["applicable_topics"] == ["revenge", "system"]
    assert template["success_cases"] == ["Source story publishable draft"]
    assert dashboard["favorite_structure_templates"][0]["tags"] == ["revenge", "payoff"]


def test_project_library_summaries_include_production_stage_for_kanban(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [],
            "imitation_projects": [
                {
                    "id": "reference-project",
                    "name": "Reference only",
                    "generated_drafts": [],
                    "created_at": "2026-06-09T12:00:00+00:00",
                },
                {
                    "id": "review-project",
                    "name": "Needs review",
                    "generated_drafts": [
                        {
                            "id": "draft-review",
                            "status": "needs_review",
                            "similarity_report": {
                                "risk_level": "medium",
                                "quality_gate": {"status": "needs_revision"},
                            },
                        }
                    ],
                    "created_at": "2026-06-09T12:01:00+00:00",
                },
                {
                    "id": "revision-project",
                    "name": "Needs revision",
                    "generated_drafts": [
                        {
                            "id": "draft-revision",
                            "status": "needs_review",
                            "similarity_report": {
                                "risk_level": "high",
                                "quality_gate": {"status": "blocked"},
                            },
                        }
                    ],
                    "latest_similarity_report": {
                        "risk_level": "high",
                        "quality_gate": {"status": "blocked"},
                    },
                    "created_at": "2026-06-09T12:02:00+00:00",
                },
                {
                    "id": "publishable-project",
                    "name": "Publishable",
                    "generated_drafts": [
                        {
                            "id": "draft-publishable",
                            "status": "publishable",
                            "similarity_report": {
                                "risk_level": "low",
                                "quality_gate": {"status": "pass"},
                            },
                        }
                    ],
                    "created_at": "2026-06-09T12:03:00+00:00",
                },
                {
                    "id": "discarded-project",
                    "name": "Discarded",
                    "generated_drafts": [
                        {
                            "id": "draft-discarded",
                            "status": "discarded",
                            "similarity_report": {"risk_level": "low"},
                        }
                    ],
                    "created_at": "2026-06-09T12:04:00+00:00",
                },
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    summaries = {item["id"]: item["production_stage"] for item in response.json()["imitation_project_summaries"]}
    assert summaries == {
        "reference-project": "reference",
        "review-project": "needs_review",
        "revision-project": "needs_revision",
        "publishable-project": "publishable",
        "discarded-project": "discarded",
    }


def test_project_library_bulk_updates_latest_draft_status_and_exports_markdown(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [],
            "imitation_projects": [
                {
                    "id": "imitate-1",
                    "name": "Draft passed gate",
                    "source_video_title": "Source one",
                    "direction": "New setting",
                    "output_type": "short_fiction",
                    "reference_markdown": "Reference package one",
                    "generated_drafts": [
                        {
                            "id": "draft-1",
                            "title": "Draft one",
                            "status": "needs_review",
                            "draft_text": "Draft body one",
                            "similarity_report": {
                                "risk_level": "low",
                                "text_overlap_percent": 2.0,
                                "quality_gate": {
                                    "status": "pass",
                                    "passed": True,
                                    "failed_checks": [],
                                },
                            },
                        }
                    ],
                    "created_at": "2026-06-09T12:00:00+00:00",
                },
                {
                    "id": "imitate-2",
                    "name": "Reference only",
                    "source_video_title": "Source two",
                    "direction": "Another setting",
                    "output_type": "short_fiction",
                    "reference_markdown": "Reference package two",
                    "generated_drafts": [],
                    "created_at": "2026-06-09T12:10:00+00:00",
                },
                {
                    "id": "imitate-3",
                    "name": "Blocked draft",
                    "source_video_title": "Source three",
                    "direction": "Another setting",
                    "output_type": "short_fiction",
                    "reference_markdown": "Reference package three",
                    "generated_drafts": [
                        {
                            "id": "draft-3",
                            "title": "Draft three",
                            "status": "needs_revision",
                            "draft_text": "Draft body three",
                            "similarity_report": {
                                "risk_level": "high",
                                "text_overlap_percent": 24.0,
                                "quality_gate": {
                                    "status": "blocked",
                                    "passed": False,
                                    "failed_checks": ["text_overlap"],
                                },
                            },
                        }
                    ],
                    "created_at": "2026-06-09T12:20:00+00:00",
                },
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    updated = client.post(
        "/api/projects/bulk-status",
        json={"project_ids": ["imitate-1", "imitate-2", "imitate-3", "missing", "imitate-1"], "status": "publishable"},
    )
    exported = client.post(
        "/api/projects/bulk-markdown",
        json={"project_ids": ["imitate-1", "imitate-2", "imitate-3"], "include_reference": True, "include_latest_draft": True},
    )
    dashboard = client.get("/api/dashboard")

    assert updated.status_code == 200
    body = updated.json()
    assert body["updated_count"] == 1
    assert body["skipped_count"] == 3
    assert body["updated"][0]["draft_id"] == "draft-1"
    assert {item["reason"] for item in body["skipped"]} == {"no_draft", "high_risk", "not_found"}
    summaries = {item["id"]: item for item in dashboard.json()["imitation_project_summaries"]}
    assert summaries["imitate-1"]["latest_draft_status"] == "publishable"
    assert summaries["imitate-3"]["latest_draft_status"] == "needs_revision"
    assert exported.status_code == 200
    export_body = exported.json()
    assert export_body["exported_count"] == 3
    assert "Reference package one" in export_body["markdown"]
    assert "Draft body one" in export_body["markdown"]
    assert "质量与风险摘要" in export_body["markdown"]
    assert "发布前检查" in export_body["markdown"]
    assert "Reference package two" in export_body["markdown"]
    assert "Draft body three" in export_body["markdown"]


def test_project_library_bulk_checks_latest_draft_risk(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [],
            "idea_cards": [],
            "reports": [],
            "imitation_projects": [
                {
                    "id": "imitate-1",
                    "name": "Needs recheck",
                    "source_video_title": "Source one",
                    "direction": "New setting",
                    "output_type": "short_fiction",
                    "reference_markdown": "Source script: Everyone looks down on the intern. The intern triggers a hidden system reward. The room falls silent.",
                    "source_script_excerpt": "Everyone looks down on the intern. The intern triggers a hidden system reward. The room falls silent.",
                    "generated_drafts": [
                        {
                            "id": "draft-1",
                            "title": "Draft one",
                            "status": "publishable",
                            "draft_text": "Everyone looks down on the intern. The intern triggers a hidden system reward. The room falls silent.",
                            "similarity_report": {"risk_level": "low", "text_overlap_percent": 0},
                            "created_at": "2026-06-09T12:00:00+00:00",
                        }
                    ],
                    "latest_similarity_report": {"risk_level": "low", "text_overlap_percent": 0},
                    "similarity_report_history": [],
                    "created_at": "2026-06-09T11:55:00+00:00",
                },
                {
                    "id": "imitate-2",
                    "name": "Reference only",
                    "generated_drafts": [],
                    "created_at": "2026-06-09T12:10:00+00:00",
                },
            ],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    checked = client.post("/api/projects/bulk-check", json={"project_ids": ["imitate-1", "imitate-2", "missing"]})
    dashboard = client.get("/api/dashboard")

    assert checked.status_code == 200
    body = checked.json()
    assert body["checked_count"] == 1
    assert body["skipped_count"] == 2
    assert body["checked"][0]["project_id"] == "imitate-1"
    assert body["checked"][0]["draft_id"] == "draft-1"
    assert body["checked"][0]["status"] == "needs_revision"
    assert body["checked"][0]["risk_level"] == "high"
    assert body["checked"][0]["quality_gate_status"] == "blocked"
    assert {item["reason"] for item in body["skipped"]} == {"no_draft", "not_found"}
    project = body["projects"][0]
    assert project["generated_drafts"][0]["similarity_report"]["risk_level"] == "high"
    assert project["generated_drafts"][0]["status"] == "needs_revision"
    assert project["similarity_report_history"][0]["draft_id"] == "draft-1"
    summary = dashboard.json()["imitation_project_summaries"][0]
    assert summary["latest_risk_level"] == "high"
    assert summary["latest_quality_gate_status"] == "blocked"


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


def test_batch_video_analysis_queues_only_pending_recent_videos(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [
                {
                    "id": "video-1",
                    "youtube_video_id": "video-1",
                    "title": "Pending video",
                    "url": "https://www.youtube.com/watch?v=pending",
                    "analysis_status": "pending",
                },
                {
                    "id": "video-2",
                    "youtube_video_id": "video-2",
                    "title": "Already analyzed",
                    "url": "https://www.youtube.com/watch?v=done",
                    "analysis_status": "complete",
                },
                {
                    "id": "video-3",
                    "youtube_video_id": "video-3",
                    "title": "Already queued",
                    "url": "https://www.youtube.com/watch?v=queued",
                    "analysis_status": "pending",
                },
            ],
            "idea_cards": [],
            "reports": [{"id": "report-1", "video_url": "https://www.youtube.com/watch?v=done"}],
            "sample_analyses": [],
            "jobs": [
                {
                    "id": "job-existing",
                    "kind": "video_analysis",
                    "status": "queued",
                    "current_step": "queued",
                    "target_url": "https://www.youtube.com/watch?v=queued",
                    "payload": {"video_url": "https://www.youtube.com/watch?v=queued"},
                }
            ],
        },
    )
    client = TestClient(create_app())

    response = client.post("/api/tasks/video-analysis/batch-start", json={"limit": 10})
    tasks = client.get("/api/tasks").json()["tasks"]

    assert response.status_code == 200
    body = response.json()
    assert body["queued_count"] == 1
    assert body["skipped_count"] == 2
    assert body["tasks"][0]["target_url"] == "https://www.youtube.com/watch?v=pending"
    assert [task["target_url"] for task in tasks].count("https://www.youtube.com/watch?v=queued") == 1


def test_batch_video_analysis_can_prioritize_topic_candidates(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [
                {
                    "id": "slow",
                    "youtube_video_id": "slow",
                    "title": "ordinary update",
                    "url": "https://www.youtube.com/watch?v=slow",
                    "published_at": "2 weeks ago",
                    "view_count": 200,
                    "analysis_status": "pending",
                },
                {
                    "id": "hot",
                    "youtube_video_id": "hot",
                    "title": "Hidden system revenge twist story",
                    "url": "https://www.youtube.com/watch?v=hot",
                    "published_at": "1 hour ago",
                    "view_count": 90000,
                    "analysis_status": "pending",
                },
            ],
            "idea_cards": [],
            "reports": [],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/tasks/video-analysis/batch-start",
        json={"limit": 1, "prioritize_candidates": True},
    )
    tasks = client.get("/api/tasks").json()["tasks"]

    assert response.status_code == 200
    body = response.json()
    assert body["prioritized"] is True
    assert body["queued_count"] == 1
    assert body["tasks"][0]["target_url"] == "https://www.youtube.com/watch?v=hot"
    assert tasks[0]["payload"]["candidate_score"] > 0
    assert tasks[0]["payload"]["candidate_reasons"]
    assert tasks[0]["payload"]["candidate_topic_group"] == "revenge"
    assert tasks[0]["payload"]["candidate_freshness_bucket"] == "fresh"
    assert tasks[0]["payload"]["candidate_view_bucket"] == "rising"
    assert tasks[0]["payload"]["candidate_viral_potential"] >= 78
    assert tasks[0]["payload"]["candidate_story_fit"] >= 90
    assert tasks[0]["payload"]["candidate_structure_reuse_value"] >= 80
    assert tasks[0]["payload"]["candidate_risk_flags"]


def test_batch_video_analysis_queues_selected_candidate_urls(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [
                {
                    "id": "one",
                    "youtube_video_id": "one",
                    "title": "Selected one",
                    "url": "https://www.youtube.com/watch?v=one",
                    "analysis_status": "pending",
                },
                {
                    "id": "two",
                    "youtube_video_id": "two",
                    "title": "Selected two",
                    "url": "https://www.youtube.com/watch?v=two",
                    "analysis_status": "pending",
                },
                {
                    "id": "done",
                    "youtube_video_id": "done",
                    "title": "Done",
                    "url": "https://www.youtube.com/watch?v=done",
                    "analysis_status": "complete",
                },
            ],
            "idea_cards": [],
            "reports": [{"id": "report-1", "video_url": "https://www.youtube.com/watch?v=done"}],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/tasks/video-analysis/batch-start",
        json={
            "limit": 10,
            "video_urls": [
                "https://www.youtube.com/watch?v=two",
                "https://www.youtube.com/watch?v=missing",
                "https://www.youtube.com/watch?v=done",
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["selected"] is True
    assert body["queued_count"] == 1
    assert body["skipped_count"] == 2
    assert body["tasks"][0]["target_url"] == "https://www.youtube.com/watch?v=two"
    assert {item["reason"] for item in body["skipped"]} == {"not_found", "already_analyzed"}


def test_dashboard_ranks_pending_topic_candidates(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    _write_workspace(
        tmp_path / "workspace-data.json",
        {
            "channels": [],
            "recent_videos": [
                {
                    "id": "hot",
                    "title": "Hidden system revenge twist story",
                    "url": "https://www.youtube.com/watch?v=hot",
                    "published_at": "1 hour ago",
                    "view_count": 90000,
                    "analysis_status": "pending",
                },
                {
                    "id": "done",
                    "title": "Already done story",
                    "url": "https://www.youtube.com/watch?v=done",
                    "published_at": "today",
                    "view_count": 200000,
                    "analysis_status": "complete",
                },
                {
                    "id": "slow",
                    "title": "ordinary update",
                    "url": "https://www.youtube.com/watch?v=slow",
                    "published_at": "2 weeks ago",
                    "view_count": 200,
                    "analysis_status": "pending",
                },
            ],
            "idea_cards": [],
            "reports": [],
            "sample_analyses": [],
            "jobs": [],
        },
    )
    client = TestClient(create_app())

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    candidates = response.json()["topic_candidates"]
    assert candidates[0]["id"] == "hot"
    assert candidates[0]["score"] > candidates[1]["score"]
    assert "done" not in {candidate["id"] for candidate in candidates}
    assert candidates[0]["reasons"]
    assert candidates[0]["topic_group"] == "revenge"
    assert candidates[0]["freshness_bucket"] == "fresh"
    assert candidates[0]["view_bucket"] == "rising"
    assert candidates[0]["viral_potential"] >= 78
    assert candidates[0]["story_fit"] >= 90
    assert candidates[0]["structure_reuse_value"] >= 80
    assert candidates[0]["recommendation_level"] == "priority"
    assert "优先分析" in candidates[0]["recommendation_summary"]
    assert "批量分析" in candidates[0]["recommended_action"]
    assert candidates[0]["risk_flags"] == ["暂无明显候选风险。"]
    assert "题材信号弱" in candidates[1]["risk_flags"][0]


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
        return {"video_id": video_id, "target_language": target_language, "translated_text": "涓枃"}

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
