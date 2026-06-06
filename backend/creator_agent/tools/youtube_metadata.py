from typing import Any
from urllib.parse import parse_qs, urlparse


def _resolve_video_id(video_url: str | None, video_id: str | None) -> str:
    if video_id:
        return video_id
    if video_url:
        parsed_url = urlparse(video_url)
        query_video_id = parse_qs(parsed_url.query).get("v", [None])[0]
        if query_video_id:
            return query_video_id

        return parsed_url.path.rstrip("/").split("/")[-1] or "manual-video"
    return "manual-video"


def get_video_metadata(video_url: str | None = None, video_id: str | None = None) -> dict[str, Any]:
    youtube_video_id = _resolve_video_id(video_url=video_url, video_id=video_id)

    return {
        "youtube_video_id": youtube_video_id,
        "title": "Manual analysis video",
        "url": video_url,
        "channel": {
            "id": "manual-channel",
            "title": "Manual channel",
        },
        "duration_seconds": 900,
        "view_count": 0,
        "like_count": 0,
        "comment_count": 0,
    }
