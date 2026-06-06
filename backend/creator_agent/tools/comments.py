from typing import Any


def collect_comments(video_id: str, mode: str = "top", limit: int = 20) -> dict[str, Any]:
    return {
        "status": "not_configured",
        "video_id": video_id,
        "mode": mode,
        "limit": limit,
        "comments": [],
        "error_message": "Comments tool is not configured.",
    }
