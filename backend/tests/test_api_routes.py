from fastapi.testclient import TestClient

from creator_agent.config import Settings
from creator_agent.main import create_app


def test_health_endpoint():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "YouTube Creator Growth Agent"}


def test_local_security_rejects_remote_host_by_default():
    client = TestClient(create_app())

    response = client.get("/api/health", headers={"Host": "192.168.1.20:8001"})

    assert response.status_code == 403
    assert response.json()["detail"].startswith("Remote access is disabled")


def test_local_security_can_be_disabled_for_explicit_remote_access(monkeypatch):
    monkeypatch.setenv("YCA_ALLOW_REMOTE_ACCESS", "true")
    client = TestClient(create_app())

    response = client.get("/api/health", headers={"Host": "192.168.1.20:8001"})

    assert response.status_code == 200


def test_dashboard_endpoint_returns_empty_state(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    client = TestClient(create_app())

    response = client.get("/api/dashboard")

    assert response.status_code == 200
    assert response.json()["recent_videos"] == []
    assert response.json()["idea_cards"] == []
    assert response.json()["comment_collector_status"] == "not_configured"


def test_health_preflight_allows_loopback_dev_origin():
    client = TestClient(create_app())

    response = client.options(
        "/api/health",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_video_analysis_endpoint_runs_local_analysis(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_TRANSCRIPT_CACHE_DIR", str(tmp_path / "transcripts"))
    monkeypatch.setenv("YCA_TRANSLATION_CACHE_DIR", str(tmp_path / "translations"))
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    monkeypatch.setattr(
        "creator_agent.agent.runtime.LLMReportAnalyzer.analyze",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("LLM disabled in this test")),
    )
    monkeypatch.setattr(
        "creator_agent.tools.youtube_metadata.collect_video_metadata",
        lambda video_url=None, video_id=None: {
            "youtube_video_id": "abc123",
            "title": "Collected title",
            "url": video_url,
            "channel": {"id": "UC123", "title": "Growth Lab", "url": "https://www.youtube.com/@growthlab"},
            "duration_seconds": None,
            "view_count": 100,
            "like_count": 10,
            "comment_count": 2,
            "collection_status": "ok",
        },
    )
    client = TestClient(create_app())

    response = client.post(
        "/api/analysis/video",
        json={"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )

    assert response.status_code == 200
    assert response.json()["job"]["status"] == "complete"
    assert response.json()["report"]["summary"]
    assert response.json()["idea_cards"]

    transcript_response = client.get("/api/reports/latest/transcript")
    assert transcript_response.status_code == 200
    assert transcript_response.json()["transcript"]["video_id"] == "abc123"
    assert transcript_response.json()["transcript"]["raw_text"]


def test_latest_report_translate_uses_openai_provider_with_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_TRANSCRIPT_CACHE_DIR", str(tmp_path / "transcripts"))
    monkeypatch.setenv("YCA_TRANSLATION_CACHE_DIR", str(tmp_path / "translations"))
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "creator_agent.agent.runtime.LLMReportAnalyzer.analyze",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("LLM disabled in this test")),
    )
    monkeypatch.setattr(
        "creator_agent.tools.youtube_metadata.collect_video_metadata",
        lambda video_url=None, video_id=None: {
            "youtube_video_id": "abc123",
            "title": "Collected title",
            "url": video_url,
            "channel": {"id": "UC123", "title": "Growth Lab", "url": "https://www.youtube.com/@growthlab"},
            "duration_seconds": None,
            "view_count": 100,
            "like_count": 10,
            "comment_count": 2,
            "collection_status": "ok",
        },
    )
    monkeypatch.setattr(
        "creator_agent.tools.transcript.collect_video_content",
        lambda video_id: {
            "status": "ready",
            "video_id": video_id,
            "transcript_text": "At the banquet, the hidden truth was revealed.",
            "transcript_source": "test_caption",
            "language": "en",
            "description": "",
            "collection_source": "test",
        },
    )
    def fake_start_background_translation(self, video_id, target_language="zh-CN", force=False):
        transcript = self.store.get_transcript(video_id)
        translation = self.store.save_translation(
            video_id=video_id,
            target_language=target_language,
            source_language=transcript["language"],
            source_text_hash="test-hash",
            translated_text="宴会上，隐藏的真相被揭露。",
            provider="openai",
            model="gpt-4.1-mini",
        )
        return {"status": "complete", "translation": translation}

    monkeypatch.setattr(
        "creator_agent.services.translation_service.TranslationService.start_background_translation",
        fake_start_background_translation,
    )
    client = TestClient(create_app())
    client.post("/api/analysis/video", json={"video_url": "https://www.youtube.com/watch?v=abc123"})

    response = client.post("/api/reports/latest/translate", json={"force": False})
    cached = client.get("/api/reports/latest/transcript")

    assert response.status_code == 200
    assert response.json()["translation"]["translated_text"] == "宴会上，隐藏的真相被揭露。"
    assert cached.json()["translation"]["provider"] == "openai"


def test_reanalyze_latest_report_uses_latest_video_url(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_TRANSCRIPT_CACHE_DIR", str(tmp_path / "transcripts"))
    monkeypatch.setenv("YCA_TRANSLATION_CACHE_DIR", str(tmp_path / "translations"))
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    calls = []

    monkeypatch.setattr(
        "creator_agent.tools.youtube_metadata.collect_video_metadata",
        lambda video_url=None, video_id=None: {
            "youtube_video_id": "abc123",
            "title": "Collected title",
            "url": video_url,
            "channel": {"id": "UC123", "title": "Growth Lab", "url": "https://www.youtube.com/@growthlab"},
            "duration_seconds": None,
            "view_count": 100,
            "like_count": 10,
            "comment_count": 2,
            "collection_status": "ok",
        },
    )
    monkeypatch.setattr(
        "creator_agent.tools.transcript.collect_video_content",
        lambda video_id: {
            "status": "ready",
            "video_id": video_id,
            "transcript_text": "This video opens with a clear promise.",
            "transcript_source": "test_caption",
            "language": "en",
            "description": "",
            "collection_source": "test",
        },
    )

    def fake_analyze(self, metadata, transcript, comments, channel_profile, metrics):
        calls.append(metadata["url"])
        raise RuntimeError("LLM disabled in this test")

    monkeypatch.setattr("creator_agent.agent.runtime.LLMReportAnalyzer.analyze", fake_analyze)
    client = TestClient(create_app())
    client.post("/api/analysis/video", json={"video_url": "https://www.youtube.com/watch?v=abc123"})

    response = client.post("/api/reports/latest/reanalyze")

    assert response.status_code == 200
    assert response.json()["job"]["status"] == "complete"
    assert calls == ["https://www.youtube.com/watch?v=abc123", "https://www.youtube.com/watch?v=abc123"]


def test_reports_history_endpoints_return_list_detail_and_transcript(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_TRANSCRIPT_CACHE_DIR", str(tmp_path / "transcripts"))
    data_path = tmp_path / "workspace-data.json"
    data_path.write_text(
        """
{
  "channels": [],
  "recent_videos": [],
  "jobs": [],
  "idea_cards": [],
  "reports": [
    {
      "id": "report-new",
      "youtube_video_id": "new123",
      "video_url": "https://www.youtube.com/watch?v=new123",
      "video_title": "New report",
      "channel_title": "Growth Lab",
      "summary": "New summary",
      "creative_breakdown": {"topic_type": "video_breakdown", "title_hook": "new title", "opening_hook": "new opening", "structure": [], "emotional_curve": []},
      "growth_judgement": {"score": 88, "reasons": ["new reason"]},
      "idea_cards": [],
      "comment_insights": {"status": "not_configured"},
      "collection_evidence": {"analysis_source": "llm", "analysis_status": "ok"},
      "created_at": "2026-06-08T12:00:00+00:00"
    },
    {
      "id": "report-old",
      "youtube_video_id": "old123",
      "video_url": "https://www.youtube.com/watch?v=old123",
      "video_title": "Old report",
      "channel_title": "Growth Lab",
      "summary": "Old summary",
      "creative_breakdown": {"topic_type": "video_breakdown", "title_hook": "old title", "opening_hook": "old opening", "structure": [], "emotional_curve": []},
      "growth_judgement": {"score": 61, "reasons": ["old reason"]},
      "idea_cards": [],
      "comment_insights": {"status": "not_configured"},
      "collection_evidence": {"analysis_source": "rule_fallback", "analysis_status": "failed"},
      "created_at": "2026-06-07T12:00:00+00:00"
    }
  ]
}
""",
        encoding="utf-8",
    )

    from creator_agent.services.transcript_store import TranscriptStore

    TranscriptStore().save_transcript(
        video_id="old123",
        video_url="https://www.youtube.com/watch?v=old123",
        title="Old report",
        source="test_caption",
        language="en",
        raw_text="Old raw script.",
    )
    client = TestClient(create_app())

    history = client.get("/api/reports")
    detail = client.get("/api/reports/report-old")
    transcript = client.get("/api/reports/report-old/transcript")
    missing = client.get("/api/reports/missing")

    assert history.status_code == 200
    assert [item["id"] for item in history.json()["reports"]] == ["report-new", "report-old"]
    assert detail.status_code == 200
    assert detail.json()["report"]["summary"] == "Old summary"
    assert transcript.status_code == 200
    assert transcript.json()["transcript"]["video_id"] == "old123"
    assert missing.status_code == 404


def test_sample_analysis_endpoints_create_and_list_samples(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_SAMPLE_CACHE_DIR", str(tmp_path / "samples"))
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))

    def fake_analyze(self, video_url, video_title="", video_id=""):
        return {
            "id": "sample-abc123",
            "video_id": video_id or "abc123",
            "video_url": video_url,
            "video_title": video_title or "Sample video",
            "status": "complete",
            "analyzed_seconds": 300,
            "frame_interval_seconds": 5,
            "frame_count": 2,
            "frames": [
                {"timestamp_seconds": 0, "path": "frame-0001.jpg"},
                {"timestamp_seconds": 5, "path": "frame-0002.jpg"},
            ],
            "visual_summary": "Fast visual promise.",
            "opening_hook": "The first minute shows the payoff before context.",
            "pacing_notes": ["Fast cuts", "Large captions"],
            "reuse_template": ["Start with consequence", "Escalate every minute"],
            "risk_notes": ["Avoid copying exact frames."],
            "created_at": "2026-06-09T00:00:00+00:00",
        }

    monkeypatch.setattr(
        "creator_agent.services.sample_analysis_service.SampleAnalysisService.analyze_video_opening",
        fake_analyze,
    )
    client = TestClient(create_app())

    created = client.post(
        "/api/samples/analyze",
        json={
            "video_url": "https://www.youtube.com/watch?v=abc123",
            "video_title": "Sample video",
            "video_id": "abc123",
        },
    )
    listed = client.get("/api/samples")

    assert created.status_code == 200
    assert created.json()["sample_analysis"]["analyzed_seconds"] == 300
    assert listed.status_code == 200
    assert listed.json()["sample_analyses"][0]["id"] == "sample-abc123"


def test_translate_report_uses_selected_report_video_id(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_TRANSCRIPT_CACHE_DIR", str(tmp_path / "transcripts"))
    data_path = tmp_path / "workspace-data.json"
    data_path.write_text(
        """
{
  "channels": [],
  "recent_videos": [],
  "jobs": [],
  "idea_cards": [],
  "reports": [
    {"id": "report-new", "youtube_video_id": "new123", "video_url": "https://www.youtube.com/watch?v=new123", "video_title": "New", "summary": "New"},
    {"id": "report-old", "youtube_video_id": "old123", "video_url": "https://www.youtube.com/watch?v=old123", "video_title": "Old", "summary": "Old"}
  ]
}
""",
        encoding="utf-8",
    )
    from creator_agent.services.transcript_store import TranscriptStore

    TranscriptStore().save_transcript(
        video_id="old123",
        video_url="https://www.youtube.com/watch?v=old123",
        title="Old",
        source="test_caption",
        language="en",
        raw_text="Old raw script.",
    )
    calls = []

    def fake_start_background_translation(self, video_id, target_language="zh-CN", force=False):
        calls.append((video_id, force))
        return {"status": "running", "translation_status": {"video_id": video_id, "status": "running"}}

    monkeypatch.setattr(
        "creator_agent.services.translation_service.TranslationService.start_background_translation",
        fake_start_background_translation,
    )
    client = TestClient(create_app())

    response = client.post("/api/reports/report-old/translate", json={"force": True})

    assert response.status_code == 200
    assert calls == [("old123", True)]


def test_report_detail_enriches_data_source_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setenv("YCA_TRANSCRIPT_CACHE_DIR", str(tmp_path / "transcripts"))
    data_path = tmp_path / "workspace-data.json"
    data_path.write_text(
        """
{
  "channels": [],
  "recent_videos": [],
  "jobs": [],
  "idea_cards": [],
  "sample_analyses": [
    {
      "id": "sample-1",
      "video_url": "https://www.youtube.com/watch?v=trust",
      "video_title": "Trust video",
      "status": "complete",
      "frame_count": 24,
      "analyzed_seconds": 300
    }
  ],
  "reports": [
    {
      "id": "report-trust",
      "youtube_video_id": "trust",
      "video_url": "https://www.youtube.com/watch?v=trust",
      "video_title": "Trust video",
      "summary": "Trust summary",
      "collection_evidence": {
        "metadata_source": "yt-dlp",
        "metadata_status": "ok",
        "transcript_source": "yt-dlp_auto_subtitle",
        "transcript_language": "en",
        "analysis_source": "rule_fallback",
        "analysis_status": "failed",
        "analysis_error": "LLM timeout"
      }
    }
  ]
}
""",
        encoding="utf-8",
    )
    from creator_agent.services.transcript_store import TranscriptStore

    TranscriptStore().save_transcript(
        video_id="trust",
        video_url="https://www.youtube.com/watch?v=trust",
        title="Trust video",
        source="yt-dlp_auto_subtitle",
        language="en",
        raw_text="This is the original transcript.",
    )
    client = TestClient(create_app())

    response = client.get("/api/reports/report-trust")

    assert response.status_code == 200
    evidence = response.json()["report"]["collection_evidence"]
    assert evidence["transcript_status"] == "ok"
    assert evidence["transcript_length"] == len("This is the original transcript.")
    assert evidence["is_auto_caption"] is True
    assert evidence["llm_participated"] is False
    assert evidence["used_rule_fallback"] is True
    assert evidence["frame_status"] == "ok"
    assert evidence["frame_count"] == 24


def test_ideas_endpoint_prefers_successful_llm_report_cards(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    data_path = tmp_path / "workspace-data.json"
    data_path.write_text(
        """
{
  "channels": [],
  "recent_videos": [],
  "jobs": [],
  "idea_cards": [
    {
      "id": "old-rule-card",
      "source": "Old source",
      "source_video_url": "https://www.youtube.com/watch?v=old",
      "title": "Rebuild the story hook behind: Old title",
      "angle": "story recap packaging",
      "why_it_works": "Rule fallback text.",
      "outline": ["old"],
      "risk_notes": "old",
      "score": 60
    }
  ],
  "reports": [
    {
      "id": "report-llm",
      "video_url": "https://www.youtube.com/watch?v=real",
      "video_title": "Real video",
      "collection_evidence": {"analysis_source": "llm", "analysis_status": "ok"},
      "idea_cards": [
        {
          "title": "校花买咖啡触发商业大厦返现",
          "angle": "系统流爽点复用",
          "why_it_works": "小钱变巨富的反差明确。",
          "outline": ["建立身份差", "触发返现"],
          "risk_notes": "不要照抄原片。",
          "score": 9
        }
      ]
    }
  ]
}
""",
        encoding="utf-8",
    )
    client = TestClient(create_app())

    response = client.get("/api/ideas")

    assert response.status_code == 200
    ideas = response.json()["idea_cards"]
    assert len(ideas) == 1
    assert ideas[0]["title"] == "校花买咖啡触发商业大厦返现"
    assert ideas[0]["score"] == 90
    assert ideas[0]["analysis_source"] == "llm"
    assert ideas[0]["source_report_id"] == "report-llm"


def test_prune_stale_ideas_persists_only_llm_report_cards(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    data_path = tmp_path / "workspace-data.json"
    data_path.write_text(
        """
{
  "channels": [],
  "recent_videos": [],
  "jobs": [],
  "idea_cards": [
    {"id": "old-1", "title": "Rebuild the story hook behind: Old", "score": 60},
    {"id": "old-2", "title": "Another old card", "score": 60}
  ],
  "reports": [
    {
      "id": "report-llm",
      "video_url": "https://www.youtube.com/watch?v=real",
      "video_title": "Real video",
      "collection_evidence": {"analysis_source": "llm", "analysis_status": "ok"},
      "idea_cards": [
        {
          "title": "中文 LLM 选题",
          "angle": "真实选题",
          "why_it_works": "来自 LLM 分析。",
          "outline": ["one"],
          "risk_notes": "risk",
          "score": 91
        }
      ]
    }
  ]
}
""",
        encoding="utf-8",
    )
    client = TestClient(create_app())

    response = client.post("/api/ideas/prune-stale")
    saved = data_path.read_text(encoding="utf-8")

    assert response.status_code == 200
    assert response.json()["removed_count"] == 1
    assert response.json()["idea_cards"][0]["title"] == "中文 LLM 选题"
    assert "Rebuild the story hook behind" not in saved


def test_channel_sync_requires_channel_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    client = TestClient(create_app())

    response = client.post("/api/channel/sync")

    assert response.status_code == 422


def test_channel_sync_populates_dashboard(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    monkeypatch.setenv("YCA_WORKSPACE_DATA_PATH", str(tmp_path / "workspace-data.json"))
    monkeypatch.setattr(
        "creator_agent.services.workspace_store.get_channel_recent_videos",
        lambda channel_id, channel_url: {
            "collection_status": "ok",
            "videos": [
                {
                    "youtube_video_id": "abc123",
                    "title": "First video",
                    "url": "https://www.youtube.com/watch?v=abc123",
                    "published_text": "1 day ago",
                    "view_count": 1200,
                }
            ],
        },
    )
    client = TestClient(create_app())
    client.put(
        "/api/settings",
        json={
            "channel_url": "https://www.youtube.com/@growthlab",
            "browser_engine": "playwright",
            "browser_headless": True,
            "browser_path": "",
            "browser_debug_port": None,
            "browser_cdp_url": "http://127.0.0.1:9222",
        },
    )

    response = client.post("/api/channel/sync")
    dashboard = client.get("/api/dashboard")

    assert response.status_code == 200
    assert response.json()["videos"][0]["title"] == "First video"
    assert dashboard.json()["recent_videos"][0]["title"] == "First video"


def test_settings_endpoint_returns_default_workspace_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    client = TestClient(create_app())

    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json() == {
        "channel_url": "",
        "channel_urls": [],
        "browser_engine": Settings().browser_engine,
        "browser_headless": Settings().browser_headless,
        "browser_path": "",
        "browser_debug_port": None,
        "browser_cdp_url": Settings().browser_cdp_url,
        "openai_base_url": Settings().openai_base_url,
        "openai_translation_model": Settings().openai_translation_model,
        "openai_analysis_model": Settings().openai_analysis_model,
        "openai_api_key": "",
        "openai_api_key_set": bool(Settings().openai_api_key),
        "monitor_enabled": False,
        "monitor_interval_minutes": 180,
        "monitor_auto_analyze": False,
        "monitor_auto_translate": False,
        "monitor_min_views": 0,
    }


def test_settings_endpoint_saves_workspace_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    client = TestClient(create_app())

    response = client.put(
        "/api/settings",
        json={
            "channel_url": "https://www.youtube.com/@growthlab",
            "channel_urls": ["https://www.youtube.com/@growthlab"],
            "browser_engine": "drission",
            "browser_headless": False,
            "browser_path": "C:/Program Files/Google/Chrome/Application/chrome.exe",
            "browser_debug_port": 9222,
            "browser_cdp_url": "http://127.0.0.1:9222",
            "openai_base_url": "http://localhost:53881/v1",
            "openai_translation_model": "gpt-5.5",
            "openai_analysis_model": "gpt-5.5",
            "openai_api_key": "secret-key",
            "openai_api_key_set": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["channel_url"] == "https://www.youtube.com/@growthlab"
    assert response.json()["browser_engine"] == "drission"

    saved = client.get("/api/settings")
    assert saved.status_code == 200
    assert saved.json()["channel_url"] == "https://www.youtube.com/@growthlab"
    assert saved.json()["browser_debug_port"] == 9222
    assert saved.json()["browser_cdp_url"] == "http://127.0.0.1:9222"
    assert saved.json()["openai_api_key"] == ""
    assert saved.json()["openai_api_key_set"] is True
    assert saved.json()["openai_analysis_model"] == "gpt-5.5"


def test_settings_endpoint_saves_cdp_workspace_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    client = TestClient(create_app())

    response = client.put(
        "/api/settings",
        json={
            "channel_url": "https://www.youtube.com/@growthlab",
            "channel_urls": ["https://www.youtube.com/@growthlab"],
            "browser_engine": "cdp",
            "browser_headless": False,
            "browser_path": "",
            "browser_debug_port": None,
            "browser_cdp_url": "http://127.0.0.1:9222",
            "openai_base_url": "http://localhost:53881/v1",
            "openai_translation_model": "gpt-5.5",
            "openai_analysis_model": "gpt-5.5",
            "openai_api_key": "",
            "openai_api_key_set": False,
        },
    )

    assert response.status_code == 200
    assert response.json()["browser_engine"] == "cdp"
    assert response.json()["browser_cdp_url"] == "http://127.0.0.1:9222"


def test_settings_endpoint_allows_blank_channel_url(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    client = TestClient(create_app())

    response = client.put(
        "/api/settings",
        json={
            "channel_url": "",
            "channel_urls": [],
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
        },
    )

    assert response.status_code == 200
    assert response.json()["channel_url"] == ""


def test_settings_endpoint_rejects_non_youtube_channel_url(tmp_path, monkeypatch):
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    client = TestClient(create_app())

    invalid_response = client.put(
        "/api/settings",
        json={
            "channel_url": "https://example.com/channel",
            "channel_urls": ["https://example.com/channel"],
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
        },
    )

    assert invalid_response.status_code == 422
