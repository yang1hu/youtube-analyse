from creator_agent.tools import build_default_registry
from creator_agent.tools.comments import collect_comments
from creator_agent.tools.metrics import compute_video_metrics
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
