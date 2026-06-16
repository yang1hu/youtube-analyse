from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from creator_agent.db.models import AnalysisJob, Channel, IdeaCard, SampleAnalysis, Video, VideoReport
from creator_agent.main import create_app


def _use_sqlite_database(tmp_path, monkeypatch) -> str:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'workspace.db'}"
    monkeypatch.setenv("YCA_DATABASE_URL", database_url)
    monkeypatch.setenv("YCA_WORKSPACE_SETTINGS_PATH", str(tmp_path / "workspace-settings.json"))
    monkeypatch.delenv("YCA_WORKSPACE_DATA_PATH", raising=False)
    return database_url


def _session(database_url: str):
    engine = create_engine(database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    return SessionLocal()


def test_channel_sync_persists_channel_and_videos_to_database(tmp_path, monkeypatch):
    database_url = _use_sqlite_database(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "creator_agent.services.workspace_store.get_channel_recent_videos",
        lambda channel_id, channel_url: {
            "collection_status": "ok",
            "collection_source": "browser:playwright",
            "videos": [
                {
                    "youtube_video_id": "abc123",
                    "title": "First database video",
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
            "openai_base_url": "http://localhost:53881/v1",
            "openai_translation_model": "gpt-5.5",
            "openai_analysis_model": "gpt-5.5",
            "openai_api_key": "",
            "openai_api_key_set": False,
        },
    )

    response = client.post("/api/channel/sync")
    dashboard = client.get("/api/dashboard")

    assert response.status_code == 200
    assert dashboard.json()["recent_videos"][0]["title"] == "First database video"
    assert dashboard.json()["recent_videos"][0]["published_at"] == "1 day ago"
    with _session(database_url) as session:
        channel = session.query(Channel).one()
        video = session.query(Video).one()
        assert channel.url == "https://www.youtube.com/@growthlab"
        assert video.youtube_video_id == "abc123"
        assert video.title == "First database video"


def test_database_workspace_preserves_video_channel_relationships(tmp_path, monkeypatch):
    _use_sqlite_database(tmp_path, monkeypatch)
    from creator_agent.services.database_workspace_store import DatabaseWorkspaceStore

    store = DatabaseWorkspaceStore()
    store.save(
        {
            "channels": [
                {
                    "id": "https://www.youtube.com/@alpha",
                    "title": "@alpha",
                    "url": "https://www.youtube.com/@alpha",
                    "collection_status": "ok",
                },
                {
                    "id": "https://www.youtube.com/@beta",
                    "title": "@beta",
                    "url": "https://www.youtube.com/@beta",
                    "collection_status": "ok",
                },
            ],
            "recent_videos": [
                {
                    "youtube_video_id": "alpha-video",
                    "title": "Alpha video",
                    "url": "https://www.youtube.com/watch?v=alpha",
                    "channel_title": "@alpha",
                    "channel_url": "https://www.youtube.com/@alpha",
                },
                {
                    "youtube_video_id": "beta-video",
                    "title": "Beta video",
                    "url": "https://www.youtube.com/watch?v=beta",
                    "channel_title": "@beta",
                    "channel_url": "https://www.youtube.com/@beta",
                },
            ],
            "jobs": [],
            "idea_cards": [],
            "style_profiles": [],
            "copy_drafts": [],
            "reports": [],
        }
    )

    videos = {video["youtube_video_id"]: video for video in store.load()["recent_videos"]}

    assert videos["alpha-video"]["channel_title"] == "@alpha"
    assert videos["alpha-video"]["channel_url"] == "https://www.youtube.com/@alpha"
    assert videos["beta-video"]["channel_title"] == "@beta"
    assert videos["beta-video"]["channel_url"] == "https://www.youtube.com/@beta"


def test_database_workspace_excludes_non_recent_analysis_videos_from_dashboard(tmp_path, monkeypatch):
    _use_sqlite_database(tmp_path, monkeypatch)
    from creator_agent.services.database_workspace_store import DatabaseWorkspaceStore

    store = DatabaseWorkspaceStore()
    store.save(
        {
            "channels": [
                {
                    "id": "https://www.youtube.com/@alpha",
                    "title": "@alpha",
                    "url": "https://www.youtube.com/@alpha",
                    "collection_status": "ok",
                }
            ],
            "recent_videos": [
                {
                    "youtube_video_id": "fresh-video",
                    "title": "Fresh video",
                    "url": "https://www.youtube.com/watch?v=fresh",
                    "channel_title": "@alpha",
                    "channel_url": "https://www.youtube.com/@alpha",
                    "is_recent_upload": True,
                }
            ],
            "jobs": [],
            "idea_cards": [],
            "style_profiles": [],
            "copy_drafts": [],
            "reports": [
                {
                    "id": "report-1",
                    "youtube_video_id": "old-analysis",
                    "video_url": "https://www.youtube.com/watch?v=old",
                    "video_title": "Old analysis title",
                    "summary": "summary",
                    "creative_breakdown": {"title_hook": "hook", "opening_hook": "opening", "structure": [], "emotional_curve": []},
                    "growth_judgement": {"score": 70, "reasons": []},
                    "idea_cards": [],
                    "collection_evidence": {"analysis_source": "llm", "analysis_status": "ok"},
                }
            ],
            "sample_analyses": [],
            "script_drafts": [],
        }
    )

    dashboard = store.load()

    assert [video["youtube_video_id"] for video in dashboard["recent_videos"]] == ["fresh-video"]
    assert dashboard["recent_videos"][0]["title"] == "Fresh video"


def test_video_analysis_persists_report_and_ideas_to_database(tmp_path, monkeypatch):
    database_url = _use_sqlite_database(tmp_path, monkeypatch)
    monkeypatch.setenv("YCA_TRANSCRIPT_CACHE_DIR", str(tmp_path / "transcripts"))
    monkeypatch.setenv("YCA_TRANSLATION_CACHE_DIR", str(tmp_path / "translations"))
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
            "transcript_text": "This video opens with a clear promise and then builds a strong reveal.",
            "transcript_source": "test_caption",
            "language": "en",
            "description": "",
            "collection_source": "test",
        },
    )
    client = TestClient(create_app())

    response = client.post("/api/analysis/video", json={"video_url": "https://www.youtube.com/watch?v=abc123"})
    latest = client.get("/api/reports/latest")

    assert response.status_code == 200
    assert latest.json()["report"]["video_url"] == "https://www.youtube.com/watch?v=abc123"
    with _session(database_url) as session:
        assert session.query(Video).filter_by(youtube_video_id="abc123").one()
        assert session.query(VideoReport).count() == 1
        assert session.query(VideoReport).one().external_id.startswith("report-")
        assert session.query(IdeaCard).count() >= 1
        assert session.query(IdeaCard).first().external_id
        assert session.query(AnalysisJob).one().external_id.startswith("job-")


def test_database_workspace_allows_multiple_reports_for_same_video(tmp_path, monkeypatch):
    database_url = _use_sqlite_database(tmp_path, monkeypatch)
    from creator_agent.services.database_workspace_store import DatabaseWorkspaceStore

    report = {
        "youtube_video_id": "abc123",
        "video_url": "https://www.youtube.com/watch?v=abc123",
        "video_title": "Repeated analysis",
        "summary": "summary",
        "creative_breakdown": {"title_hook": "hook", "opening_hook": "opening", "structure": [], "emotional_curve": []},
        "growth_judgement": {"score": 70, "reasons": []},
        "idea_cards": [],
        "collection_evidence": {"analysis_source": "llm", "analysis_status": "ok"},
    }
    DatabaseWorkspaceStore().save(
        {
            "channels": [],
            "recent_videos": [],
            "jobs": [],
            "idea_cards": [],
            "style_profiles": [],
            "copy_drafts": [],
            "reports": [
                {"id": "report-1", **report},
                {"id": "report-2", **report, "summary": "newer summary"},
            ],
        }
    )

    with _session(database_url) as session:
        assert session.query(Video).filter_by(youtube_video_id="abc123").count() == 1
        assert session.query(VideoReport).count() == 2
        assert {report.external_id for report in session.query(VideoReport).all()} == {"report-1", "report-2"}


def test_database_workspace_save_preserves_records_missing_from_next_snapshot(tmp_path, monkeypatch):
    database_url = _use_sqlite_database(tmp_path, monkeypatch)
    from creator_agent.services.database_workspace_store import DatabaseWorkspaceStore

    store = DatabaseWorkspaceStore()
    base_report = {
        "id": "report-1",
        "youtube_video_id": "abc123",
        "video_url": "https://www.youtube.com/watch?v=abc123",
        "video_title": "Original report",
        "summary": "summary",
        "creative_breakdown": {"title_hook": "hook", "opening_hook": "opening", "structure": [], "emotional_curve": []},
        "growth_judgement": {"score": 70, "reasons": []},
        "idea_cards": [],
        "collection_evidence": {"analysis_source": "llm", "analysis_status": "ok"},
    }
    store.save(
        {
            "channels": [],
            "recent_videos": [],
            "jobs": [],
            "idea_cards": [],
            "style_profiles": [],
            "sample_analyses": [
                {
                    "id": "sample-1",
                    "video_url": "https://www.youtube.com/watch?v=abc123",
                    "video_title": "Sample one",
                    "status": "complete",
                }
            ],
            "copy_drafts": [],
            "script_drafts": [],
            "reports": [base_report],
        }
    )
    store.save(
        {
            "channels": [],
            "recent_videos": [],
            "jobs": [],
            "idea_cards": [],
            "style_profiles": [],
            "sample_analyses": [],
            "copy_drafts": [],
            "script_drafts": [],
            "reports": [
                {
                    **base_report,
                    "id": "report-2",
                    "summary": "new summary",
                }
            ],
        }
    )

    with _session(database_url) as session:
        assert session.query(Video).filter_by(youtube_video_id="abc123").count() == 1
        assert session.query(VideoReport).count() == 2
        assert session.query(VideoReport).filter_by(external_id="report-1").count() == 1
        assert session.query(VideoReport).filter_by(external_id="report-2").count() == 1
        assert session.query(SampleAnalysis).filter_by(external_id="sample-1").count() == 1


def test_dashboard_prefers_configured_channel_over_stale_database_channel(tmp_path, monkeypatch):
    _use_sqlite_database(tmp_path, monkeypatch)
    from creator_agent.services.database_workspace_store import DatabaseWorkspaceStore
    from creator_agent.services.settings_service import WorkspaceSettings, WorkspaceSettingsService
    from creator_agent.services.workspace_store import WorkspaceStore

    DatabaseWorkspaceStore().save(
        {
            "channels": [
                {
                    "id": "https://www.youtube.com/@oldchannel",
                    "title": "@oldchannel",
                    "url": "https://www.youtube.com/@oldchannel",
                    "collection_status": "ok",
                }
            ],
            "recent_videos": [
                {
                    "youtube_video_id": "old-video",
                    "title": "Old video",
                    "url": "https://www.youtube.com/watch?v=old",
                    "channel_title": "@oldchannel",
                }
            ],
            "jobs": [],
            "idea_cards": [],
            "style_profiles": [],
            "copy_drafts": [],
            "reports": [],
        }
    )
    WorkspaceSettingsService().save(
        WorkspaceSettings(
            channel_url="https://www.youtube.com/@newchannel",
            channel_urls=["https://www.youtube.com/@newchannel"],
            browser_engine="playwright",
            browser_headless=True,
            browser_path="",
            browser_debug_port=None,
            browser_cdp_url="http://127.0.0.1:9222",
            openai_base_url="http://localhost:53881/v1",
            openai_translation_model="gpt-5.5",
            openai_analysis_model="gpt-5.5",
            openai_api_key="",
            openai_api_key_set=False,
        )
    )

    dashboard = WorkspaceStore().dashboard()

    assert dashboard["channels"][0]["url"] == "https://www.youtube.com/@newchannel"
    assert dashboard["channels"][0]["title"] == "@newchannel"
    assert dashboard["recent_videos"] == []
