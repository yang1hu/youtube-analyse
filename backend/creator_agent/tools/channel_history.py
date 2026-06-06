from typing import Any


def get_channel_recent_videos(channel_id: str, limit: int = 10) -> dict[str, Any]:
    return {
        "channel_id": channel_id,
        "limit": limit,
        "videos": [],
    }


def get_channel_profile(channel_id: str) -> dict[str, Any]:
    return {
        "channel_id": channel_id,
        "title": "",
        "description": "",
        "subscriber_count": 0,
        "avg_view_count": 0,
    }
