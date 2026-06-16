from typing import Any

from creator_agent.collectors.video_content import VideoContentUnavailable, collect_video_content


def get_transcript(video_id: str) -> dict[str, Any]:
    try:
        content = collect_video_content(video_id=video_id)
    except (RuntimeError, VideoContentUnavailable) as exc:
        return {
            "status": "ready",
            "video_id": video_id,
            "text": "Transcript unavailable. Continue analysis from metadata and description.",
            "source": "fallback",
            "description": "",
            "error_message": str(exc),
        }

    transcript_text = str(content.get("transcript_text") or "").strip()
    if not transcript_text:
        transcript_text = "Transcript unavailable. Continue analysis from metadata and description."

    return {
        "status": "ready",
        "video_id": video_id,
        "text": transcript_text,
        "source": content.get("transcript_source") or "unavailable",
        "language": content.get("language") or "",
        "description": content.get("description") or "",
        "title": content.get("title") or "",
        "collection_source": content.get("collection_source") or "",
    }
