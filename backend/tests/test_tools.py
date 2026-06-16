from creator_agent.tools import build_default_registry
from creator_agent.tools.comments import collect_comments
from creator_agent.tools.channel_history import get_channel_profile, get_channel_recent_videos
from creator_agent.tools.metrics import compute_video_metrics
from creator_agent.tools.transcript import get_transcript
from creator_agent.tools.youtube_metadata import BrowserCollectionUnavailable
from creator_agent.tools.youtube_metadata import get_video_metadata


def test_default_registry_exposes_mvp_tools():
    registry = build_default_registry()

    assert sorted(registry.names()) == [
        "compute_video_metrics",
        "get_channel_profile",
        "get_channel_recent_videos",
        "get_comments",
        "get_transcript",
        "get_video_metadata",
    ]


def test_comments_tool_is_first_class_but_not_configured():
    result = collect_comments(video_id="abc123", mode="top", limit=20)

    assert result["status"] == "not_configured"
    assert result["comments"] == []
    assert "not configured" in result["error_message"]


def test_compute_video_metrics_is_deterministic():
    metrics = compute_video_metrics(
        video={"view_count": 12000, "like_count": 900, "comment_count": 300, "title": "How I grew my channel"},
        channel_baseline={"avg_view_count": 6000},
    )

    assert metrics["relative_views"] == 2.0
    assert metrics["engagement_rate"] == 0.1
    assert metrics["title_length"] == 21
    assert metrics["performance_band"] == "high"


def test_get_video_metadata_extracts_common_url_video_ids():
    urls = [
        "https://youtu.be/abc123",
        "https://www.youtube.com/watch?v=abc123",
        "https://youtube.com/watch?v=abc123&feature=share",
    ]

    for url in urls:
        metadata = get_video_metadata(video_url=url)

        assert metadata["youtube_video_id"] == "abc123"


def test_get_video_metadata_prefers_explicit_video_id():
    metadata = get_video_metadata(video_url="https://www.youtube.com/watch?v=url-id", video_id="explicit-id")

    assert metadata["youtube_video_id"] == "explicit-id"


def test_get_video_metadata_uses_browser_collector_when_available(monkeypatch):
    def fake_collect_video_metadata(video_url=None, video_id=None):
        return {
            "youtube_video_id": video_id or "abc123",
            "title": "Collected title",
            "url": video_url,
            "channel": {"id": "UC123", "title": "Growth Lab", "url": "https://www.youtube.com/@growthlab"},
            "duration_seconds": None,
            "view_count": 12345,
            "like_count": 0,
            "comment_count": 0,
            "collection_status": "ok",
            "collection_source": "browser",
        }

    monkeypatch.setattr("creator_agent.tools.youtube_metadata.collect_video_metadata", fake_collect_video_metadata)

    metadata = get_video_metadata(video_url="https://www.youtube.com/watch?v=abc123")

    assert metadata["title"] == "Collected title"
    assert metadata["collection_status"] == "ok"
    assert metadata["collection_source"] == "browser"


def test_get_video_metadata_falls_back_when_browser_collector_is_unavailable(monkeypatch):
    def fake_collect_video_metadata(video_url=None, video_id=None):
        raise BrowserCollectionUnavailable("browser unavailable")

    monkeypatch.setattr("creator_agent.tools.youtube_metadata.collect_video_metadata", fake_collect_video_metadata)

    metadata = get_video_metadata(video_url="https://www.youtube.com/watch?v=abc123")

    assert metadata["youtube_video_id"] == "abc123"
    assert metadata["title"] == "Manual analysis video"
    assert metadata["collection_status"] == "browser_unavailable"
    assert metadata["collection_error"] == "browser unavailable"


def test_get_transcript_uses_video_content_collector(monkeypatch):
    monkeypatch.setattr(
        "creator_agent.tools.transcript.collect_video_content",
        lambda video_id: {
            "status": "ready",
            "video_id": video_id,
            "title": "Collected title",
            "description": "Collected description",
            "transcript_text": "Human caption text.",
            "transcript_source": "yt-dlp_subtitle",
            "language": "en",
        },
    )

    transcript = get_transcript(video_id="abc123")

    assert transcript["status"] == "ready"
    assert transcript["text"] == "Human caption text."
    assert transcript["source"] == "yt-dlp_subtitle"
    assert transcript["description"] == "Collected description"


def test_get_transcript_falls_back_when_content_collector_fails(monkeypatch):
    def fake_collect_video_content(video_id):
        raise RuntimeError("temporary YouTube limit")

    monkeypatch.setattr("creator_agent.tools.transcript.collect_video_content", fake_collect_video_content)

    transcript = get_transcript(video_id="abc123")

    assert transcript["status"] == "ready"
    assert transcript["text"] == "Transcript unavailable. Continue analysis from metadata and description."
    assert transcript["source"] == "fallback"
    assert transcript["error_message"] == "temporary YouTube limit"


def test_channel_history_tools_use_browser_collector_when_channel_url_is_available(monkeypatch):
    def fake_collect_channel_profile(channel_url):
        return {
            "channel_id": "UC123",
            "title": "Growth Lab",
            "description": "Creator strategy channel",
            "url": channel_url,
            "subscriber_count": 0,
            "avg_view_count": 0,
            "collection_status": "ok",
        }

    def fake_collect_channel_recent_videos(channel_url, limit=10):
        return {
            "channel_url": channel_url,
            "limit": limit,
            "videos": [{"youtube_video_id": "abc123", "title": "Collected video"}],
            "collection_status": "ok",
        }

    monkeypatch.setattr("creator_agent.tools.channel_history.collect_channel_profile", fake_collect_channel_profile)
    monkeypatch.setattr(
        "creator_agent.tools.channel_history.collect_channel_recent_videos",
        fake_collect_channel_recent_videos,
    )

    profile = get_channel_profile(channel_id="UC123", channel_url="https://www.youtube.com/@growthlab")
    recent = get_channel_recent_videos(channel_id="UC123", channel_url="https://www.youtube.com/@growthlab", limit=1)

    assert profile["title"] == "Growth Lab"
    assert recent["videos"] == [{"youtube_video_id": "abc123", "title": "Collected video"}]
