from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from creator_agent.db.models import Channel, Video


class ChannelRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(self, youtube_channel_id: str, title: str, url: str) -> Channel:
        channel = self.session.query(Channel).filter_by(youtube_channel_id=youtube_channel_id).one_or_none()
        if channel is not None:
            return channel

        channel = Channel(
            youtube_channel_id=youtube_channel_id,
            title=title,
            url=url,
            status="active",
        )
        self.session.add(channel)
        self.session.flush()
        return channel


class VideoRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create(self, channel: Channel, metadata: dict[str, Any]) -> Video:
        youtube_video_id = str(metadata.get("youtube_video_id") or metadata.get("video_id") or "")
        video = self.session.query(Video).filter_by(youtube_video_id=youtube_video_id).one_or_none()
        if video is not None:
            return video

        video = Video(
            channel=channel,
            youtube_video_id=youtube_video_id,
            title=str(metadata.get("title") or "Untitled video"),
            url=str(metadata.get("url") or ""),
            published_at=self._published_at(metadata.get("published_at")),
            published_text=self._published_text(metadata),
            duration_seconds=metadata.get("duration_seconds"),
            view_count=metadata.get("view_count"),
            like_count=metadata.get("like_count"),
            comment_count=metadata.get("comment_count"),
            transcript=metadata.get("transcript"),
            transcript_status="ready",
            analysis_status="pending",
        )
        self.session.add(video)
        self.session.flush()
        return video

    def _published_at(self, value: Any) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    def _published_text(self, metadata: dict[str, Any]) -> str:
        value = metadata.get("published_text") or metadata.get("published_at") or ""
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)
