from typing import Any


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def compute_video_metrics(video: dict[str, Any], channel_baseline: dict[str, Any]) -> dict[str, Any]:
    view_count = _as_int(video.get("view_count"))
    like_count = _as_int(video.get("like_count"))
    comment_count = _as_int(video.get("comment_count"))
    avg_view_count = _as_int(channel_baseline.get("avg_view_count"))

    relative_views = round(view_count / avg_view_count, 2) if avg_view_count else 0.0
    engagement_rate = round((like_count + comment_count) / view_count, 4) if view_count else 0.0

    if relative_views >= 1.5:
        performance_band = "high"
    elif relative_views >= 0.75:
        performance_band = "normal"
    else:
        performance_band = "low"

    title = str(video.get("title") or "")

    return {
        "view_count": view_count,
        "like_count": like_count,
        "comment_count": comment_count,
        "avg_view_count": avg_view_count,
        "relative_views": relative_views,
        "engagement_rate": engagement_rate,
        "title_length": len(title),
        "performance_band": performance_band,
    }
