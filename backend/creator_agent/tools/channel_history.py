from typing import Any

from creator_agent.collectors.youtube_browser import (
    BrowserCollectionUnavailable,
    collect_channel_profile,
    collect_channel_recent_videos,
)


def get_channel_recent_videos(channel_id: str, limit: int = 10, channel_url: str | None = None) -> dict[str, Any]:
    if channel_url:
        try:
            result = collect_channel_recent_videos(channel_url=channel_url, limit=limit)
            return {"channel_id": channel_id, **result}
        except BrowserCollectionUnavailable as exc:
            collection_status = "browser_unavailable"
            collection_error = str(exc)
        else:
            collection_status = "ok"
            collection_error = ""
    else:
        collection_status = "missing_channel_url"
        collection_error = "Channel URL is required for browser collection."

    return {
        "channel_id": channel_id,
        "channel_url": channel_url,
        "limit": limit,
        "videos": [],
        "collection_status": collection_status,
        "collection_source": "stub",
        "collection_error": collection_error,
    }


def get_channel_profile(channel_id: str, channel_url: str | None = None) -> dict[str, Any]:
    if channel_url:
        try:
            result = collect_channel_profile(channel_url=channel_url)
            return {"channel_id": result.get("channel_id") or channel_id, **result}
        except BrowserCollectionUnavailable as exc:
            collection_status = "browser_unavailable"
            collection_error = str(exc)
        else:
            collection_status = "ok"
            collection_error = ""
    else:
        collection_status = "missing_channel_url"
        collection_error = "Channel URL is required for browser collection."

    return {
        "channel_id": channel_id,
        "channel_url": channel_url,
        "title": "",
        "description": "",
        "subscriber_count": 0,
        "avg_view_count": 0,
        "collection_status": collection_status,
        "collection_source": "stub",
        "collection_error": collection_error,
    }
