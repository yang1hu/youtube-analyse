from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from creator_agent.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Channel(TimestampMixin, Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    youtube_channel_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    videos: Mapped[list["Video"]] = relationship(back_populates="channel", cascade="all, delete-orphan")
    profile: Mapped["ChannelProfile | None"] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Video(TimestampMixin, Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), index=True, nullable=False)
    youtube_video_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    view_count: Mapped[int | None] = mapped_column(Integer)
    like_count: Mapped[int | None] = mapped_column(Integer)
    comment_count: Mapped[int | None] = mapped_column(Integer)
    transcript: Mapped[str | None] = mapped_column(Text)
    transcript_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    analysis_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    channel: Mapped["Channel"] = relationship(back_populates="videos")
    report: Mapped["VideoReport | None"] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
        uselist=False,
    )
    idea_cards: Mapped[list["IdeaCard"]] = relationship(back_populates="source_video", cascade="all, delete-orphan")
    comments: Mapped[list["Comment"]] = relationship(back_populates="video", cascade="all, delete-orphan")


class AnalysisJob(TimestampMixin, Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    current_step: Mapped[str] = mapped_column(String(100), default="queued", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VideoReport(TimestampMixin, Base):
    __tablename__ = "video_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), unique=True, index=True, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    topic_type: Mapped[str | None] = mapped_column(String(100))
    title_hook: Mapped[str | None] = mapped_column(String(255))
    opening_hook: Mapped[str | None] = mapped_column(String(255))
    structure_analysis: Mapped[list[str] | None] = mapped_column(JSON)
    emotional_curve: Mapped[list[str] | None] = mapped_column(JSON)
    monetization_intent: Mapped[str | None] = mapped_column(String(255))
    growth_score: Mapped[int | None] = mapped_column(Integer)
    growth_judgement: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    video: Mapped["Video"] = relationship(back_populates="report")


class IdeaCard(TimestampMixin, Base):
    __tablename__ = "idea_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    angle: Mapped[str | None] = mapped_column(String(255))
    why_it_works: Mapped[str | None] = mapped_column(Text)
    suggested_outline: Mapped[list[str] | None] = mapped_column(JSON)
    risk_notes: Mapped[str | None] = mapped_column(Text)
    score: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)

    source_video: Mapped["Video"] = relationship(back_populates="idea_cards")


class ChannelProfile(TimestampMixin, Base):
    __tablename__ = "channel_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), unique=True, index=True, nullable=False)
    positioning: Mapped[str | None] = mapped_column(Text)
    audience: Mapped[str | None] = mapped_column(Text)
    content_pillars: Mapped[list[str] | None] = mapped_column(JSON)
    strengths: Mapped[list[str] | None] = mapped_column(JSON)
    gaps: Mapped[list[str] | None] = mapped_column(JSON)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    channel: Mapped["Channel"] = relationship(back_populates="profile")


class Comment(TimestampMixin, Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True, nullable=False)
    youtube_comment_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    author_name: Mapped[str | None] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    like_count: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    video: Mapped["Video"] = relationship(back_populates="comments")
    insight: Mapped["CommentInsight | None"] = relationship(
        back_populates="comment",
        cascade="all, delete-orphan",
        uselist=False,
    )


class CommentInsight(TimestampMixin, Base):
    __tablename__ = "comment_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comment_id: Mapped[int] = mapped_column(ForeignKey("comments.id"), unique=True, index=True, nullable=False)
    sentiment: Mapped[str | None] = mapped_column(String(50))
    intent: Mapped[str | None] = mapped_column(String(100))
    pain_points: Mapped[list[str] | None] = mapped_column(JSON)
    opportunities: Mapped[list[str] | None] = mapped_column(JSON)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    comment: Mapped["Comment"] = relationship(back_populates="insight")
