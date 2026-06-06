from creator_agent.tools import build_default_registry
from creator_agent.tools.comments import collect_comments
from creator_agent.tools.metrics import compute_video_metrics


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
