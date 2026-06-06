from typing import Any


def get_transcript(video_id: str) -> dict[str, Any]:
    return {
        "status": "ready",
        "video_id": video_id,
        "text": "Stub transcript text for manual analysis.",
    }
