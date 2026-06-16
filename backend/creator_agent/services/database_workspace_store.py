from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from creator_agent.config import Settings
from creator_agent.db.models import (
    AnalysisJob,
    Channel,
    Comment,
    CommentInsight,
    CopyDraft,
    IdeaCard,
    SampleAnalysis,
    ScriptDraft,
    StyleProfile,
    Video,
    VideoReport,
)
from creator_agent.db.session import build_session_factory
from creator_agent.services.workspace_shapes import empty_workspace_data


class DatabaseWorkspaceStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.session_factory: sessionmaker[Session] = build_session_factory(self.settings)

    def load(self) -> dict[str, Any]:
        with self.session_factory() as session:
            return {
                "channels": [self._channel_to_dict(channel) for channel in session.query(Channel).order_by(Channel.id.desc()).all()],
                "recent_videos": [
                    self._video_to_dict(video)
                    for video in session.query(Video)
                    .filter_by(is_recent_upload=True)
                    .order_by(Video.id.desc())
                    .all()
                ],
                "idea_cards": [self._idea_to_dict(idea) for idea in session.query(IdeaCard).order_by(IdeaCard.id.desc()).all()],
                "style_profiles": [profile.raw_json for profile in session.query(StyleProfile).order_by(StyleProfile.id.desc()).all()],
                "sample_analyses": [sample.raw_json for sample in session.query(SampleAnalysis).order_by(SampleAnalysis.id.desc()).all()],
                "copy_drafts": [draft.raw_json for draft in session.query(CopyDraft).order_by(CopyDraft.id.desc()).all()],
                "script_drafts": [draft.raw_json for draft in session.query(ScriptDraft).order_by(ScriptDraft.id.desc()).all()],
                "jobs": [self._job_to_dict(job) for job in session.query(AnalysisJob).order_by(AnalysisJob.id.desc()).all()],
                "reports": [self._report_to_dict(report) for report in session.query(VideoReport).order_by(VideoReport.id.desc()).all()],
            }

    def save(self, data: dict[str, Any]) -> dict[str, Any]:
        normalized = {**empty_workspace_data(), **data}
        with self.session_factory() as session:
            self._upsert_snapshot(session, normalized)
            session.commit()
        return normalized

    def _upsert_snapshot(self, session: Session, data: dict[str, Any]) -> None:
        channel_by_key: dict[str, Channel] = self._existing_channels(session)
        for channel_data in data["channels"]:
            channel = self._upsert_channel(session, channel_data)
            for key in {
                str(channel_data.get("id") or ""),
                str(channel_data.get("url") or ""),
                str(channel_data.get("title") or ""),
                channel.youtube_channel_id,
                channel.title,
            }:
                if key:
                    channel_by_key[key] = channel

        default_channel = next(iter(channel_by_key.values()), None)
        video_by_url: dict[str, Video] = {
            video.url: video for video in session.query(Video).all() if video.url
        }
        video_by_youtube_id: dict[str, Video] = {
            video.youtube_video_id: video for video in session.query(Video).all() if video.youtube_video_id
        }
        for video_data in data["recent_videos"]:
            channel = self._channel_for_video(session, video_data, channel_by_key, default_channel)
            default_channel = default_channel or channel
            video = self._upsert_video(session, channel, video_data)
            if video.url:
                video_by_url[video.url] = video
            if video.youtube_video_id:
                video_by_youtube_id[video.youtube_video_id] = video

        for job_data in data["jobs"]:
            self._upsert_job(session, job_data)

        report_video_by_id: dict[str, Video] = {}
        for report_data in data["reports"]:
            video = self._video_for_report(session, report_data, default_channel, video_by_url, video_by_youtube_id)
            if video.url:
                video_by_url[video.url] = video
            if video.youtube_video_id:
                video_by_youtube_id[video.youtube_video_id] = video
            report = self._upsert_report(session, video, report_data)
            session.flush()
            if report_data.get("id"):
                report_video_by_id[str(report_data["id"])] = video

        for idea_data in data["idea_cards"]:
            video = self._video_for_idea(default_channel, video_by_url, report_video_by_id, idea_data)
            if video is not None:
                self._upsert_idea(session, video, idea_data)

        for style_data in data["style_profiles"]:
            if isinstance(style_data, dict):
                self._upsert_external_json(
                    session,
                    StyleProfile,
                    str(style_data.get("id") or f"style-{len(session.new) + 1}"),
                    {
                        "name": str(style_data.get("name") or "Style profile"),
                        "source_report_id": str(style_data.get("source_report_id") or ""),
                        "raw_json": style_data,
                    },
                )

        for sample_data in data["sample_analyses"]:
            if isinstance(sample_data, dict):
                self._upsert_external_json(
                    session,
                    SampleAnalysis,
                    str(sample_data.get("id") or f"sample-{len(session.new) + 1}"),
                    {
                        "video_url": str(sample_data.get("video_url") or ""),
                        "video_title": str(sample_data.get("video_title") or "Sample analysis"),
                        "status": str(sample_data.get("status") or "complete"),
                        "raw_json": sample_data,
                    },
                )

        for draft_data in data["copy_drafts"]:
            if isinstance(draft_data, dict):
                self._upsert_external_json(
                    session,
                    CopyDraft,
                    str(draft_data.get("id") or f"draft-{len(session.new) + 1}"),
                    {
                        "style_external_id": str(draft_data.get("style_id") or ""),
                        "idea_external_id": str(draft_data.get("idea_id") or ""),
                        "title": str(draft_data.get("title") or "Copy draft"),
                        "provider": str(draft_data.get("provider") or ""),
                        "model": str(draft_data.get("model") or ""),
                        "raw_json": draft_data,
                    },
                )

        for script_data in data["script_drafts"]:
            if isinstance(script_data, dict):
                self._upsert_external_json(
                    session,
                    ScriptDraft,
                    str(script_data.get("id") or f"script-{len(session.new) + 1}"),
                    {
                        "idea_external_id": str(script_data.get("idea_id") or ""),
                        "style_external_id": str(script_data.get("style_id") or ""),
                        "parent_external_id": str(script_data.get("parent_id") or ""),
                        "version": self._as_int(script_data.get("version") or 1),
                        "title": str(script_data.get("selected_title") or "Script draft"),
                        "raw_json": script_data,
                    },
                )

    def _existing_channels(self, session: Session) -> dict[str, Channel]:
        channels: dict[str, Channel] = {}
        for channel in session.query(Channel).all():
            for key in {channel.youtube_channel_id, channel.url, channel.title}:
                if key:
                    channels[key] = channel
        return channels

    def _channel_for_video(
        self,
        session: Session,
        video_data: dict[str, Any],
        channel_by_key: dict[str, Channel],
        default_channel: Channel | None,
    ) -> Channel:
        channel_url = str(video_data.get("channel_url") or "")
        channel_title = str(video_data.get("channel_title") or "")
        for key in (channel_url, channel_title):
            if key and key in channel_by_key:
                return channel_by_key[key]

        if channel_url or channel_title:
            channel = self._create_channel(
                session,
                {
                    "id": channel_url or channel_title,
                    "title": channel_title or channel_url.rstrip("/").split("/")[-1],
                    "url": channel_url,
                    "collection_status": "configured",
                },
            )
            for key in {channel_url, channel_title, channel.youtube_channel_id, channel.title}:
                if key:
                    channel_by_key[key] = channel
            return channel

        return default_channel or self._create_channel(
            session,
            {
                "id": "manual-channel",
                "title": "Manual channel",
                "url": "",
            },
        )

    def _upsert_channel(self, session: Session, channel_data: dict[str, Any]) -> Channel:
        channel_id = str(channel_data.get("id") or channel_data.get("url") or "manual-channel")
        channel = session.query(Channel).filter_by(youtube_channel_id=channel_id).one_or_none()
        if channel is None:
            channel = self._create_channel(session, channel_data)
            return channel
        channel.title = str(channel_data.get("title") or "Untitled channel")
        channel.url = str(channel_data.get("url") or "")
        channel.description = str(channel_data.get("collection_error") or channel_data.get("description") or "")
        channel.status = str(channel_data.get("collection_status") or channel_data.get("status") or "active")
        session.flush()
        return channel

    def _upsert_video(self, session: Session, channel: Channel, video_data: dict[str, Any]) -> Video:
        youtube_video_id = str(video_data.get("youtube_video_id") or video_data.get("id") or video_data.get("url") or "manual-video")
        video = session.query(Video).filter_by(youtube_video_id=youtube_video_id).one_or_none()
        if video is None:
            return self._create_video(session, channel, {**video_data, "is_recent_upload": True})
        video.channel = channel
        video.title = str(video_data.get("title") or "Untitled video")
        video.url = str(video_data.get("url") or "")
        video.published_at = self._parse_datetime(video_data.get("published_at"))
        video.published_text = self._published_text(video_data)
        video.duration_seconds = self._as_int_or_none(video_data.get("duration_seconds"))
        video.view_count = self._as_int_or_none(video_data.get("view_count"))
        video.like_count = self._as_int_or_none(video_data.get("like_count"))
        video.comment_count = self._as_int_or_none(video_data.get("comment_count"))
        video.transcript = video_data.get("transcript")
        video.transcript_status = str(video_data.get("transcript_status") or "pending")
        video.analysis_status = str(video_data.get("analysis_status") or "pending")
        video.is_recent_upload = True
        session.flush()
        return video

    def _upsert_job(self, session: Session, job_data: dict[str, Any]) -> AnalysisJob:
        external_id = str(job_data.get("id") or "")
        job = self._job_by_external_id(session, external_id) if external_id else None
        if job is None:
            job = self._create_job(job_data)
            session.add(job)
        else:
            job.external_id = external_id or job.external_id
            job.type = str(job_data.get("kind") or job_data.get("type") or "video_analysis")
            job.target_type = str(job_data.get("target_type") or "video_url")
            job.target_id = self._as_int(job_data.get("target_id"))
            job.status = str(job_data.get("status") or "queued")
            job.current_step = str(job_data.get("current_step") or job_data.get("status") or "queued")
            job.error_message = job_data.get("error_message")
            job.payload = {**job_data, "external_id": job_data.get("id")}
            job.result_json = job_data.get("result_json")
            job.started_at = self._parse_datetime(job_data.get("started_at"))
            job.finished_at = self._parse_datetime(job_data.get("finished_at"))
        session.flush()
        return job

    def _upsert_report(self, session: Session, video: Video, report_data: dict[str, Any]) -> VideoReport:
        external_id = str(report_data.get("id") or "")
        report = self._report_by_external_id(session, external_id) if external_id else None
        if report is None:
            report = self._create_report(video, report_data)
            session.add(report)
        else:
            self._apply_report(report, video, report_data)
        session.flush()
        return report

    def _apply_report(self, report: VideoReport, video: Video, report_data: dict[str, Any]) -> None:
        creative = report_data.get("creative_breakdown") if isinstance(report_data.get("creative_breakdown"), dict) else {}
        growth = report_data.get("growth_judgement") if isinstance(report_data.get("growth_judgement"), dict) else {}
        report.video = video
        report.external_id = str(report_data.get("id") or "") or report.external_id
        report.summary = str(report_data.get("summary") or "")
        report.topic_type = creative.get("topic_type")
        report.title_hook = creative.get("title_hook")
        report.opening_hook = creative.get("opening_hook")
        report.structure_analysis = creative.get("structure") if isinstance(creative.get("structure"), list) else []
        report.emotional_curve = creative.get("emotional_curve") if isinstance(creative.get("emotional_curve"), list) else []
        report.monetization_intent = creative.get("monetization_intent")
        report.growth_score = self._as_int_or_none(growth.get("score"))
        report.growth_judgement = growth
        report.raw_json = report_data

    def _upsert_idea(self, session: Session, video: Video, idea_data: dict[str, Any]) -> IdeaCard:
        idea = self._idea_by_external_id(session, str(idea_data.get("id") or ""))
        if idea is None:
            idea = (
                session.query(IdeaCard)
                .filter_by(source_video_id=video.id, title=str(idea_data.get("title") or "Untitled idea"))
                .one_or_none()
            )
        if idea is None:
            idea = self._create_idea(video, idea_data)
            session.add(idea)
        else:
            idea.external_id = str(idea_data.get("id") or "") or idea.external_id
            idea.source_video = video
            idea.title = str(idea_data.get("title") or "Untitled idea")
            idea.angle = idea_data.get("angle")
            idea.why_it_works = idea_data.get("why_it_works")
            idea.suggested_outline = idea_data.get("outline") if isinstance(idea_data.get("outline"), list) else []
            idea.risk_notes = idea_data.get("risk_notes")
            idea.score = self._as_int_or_none(idea_data.get("score"))
            idea.status = str(idea_data.get("status") or "saved")
        session.flush()
        return idea

    def _upsert_external_json(self, session: Session, model: type[Any], external_id: str, fields: dict[str, Any]) -> Any:
        record = session.query(model).filter_by(external_id=external_id).one_or_none()
        if record is None:
            record = model(external_id=external_id, **fields)
            session.add(record)
        else:
            for key, value in fields.items():
                setattr(record, key, value)
        session.flush()
        return record

    def _job_by_external_id(self, session: Session, external_id: str) -> AnalysisJob | None:
        job = session.query(AnalysisJob).filter_by(external_id=external_id).one_or_none()
        if job is not None:
            return job
        for job in session.query(AnalysisJob).all():
            payload = job.payload if isinstance(job.payload, dict) else {}
            if str(payload.get("external_id") or "") == external_id:
                job.external_id = external_id
                return job
        return None

    def _report_by_external_id(self, session: Session, external_id: str) -> VideoReport | None:
        report = session.query(VideoReport).filter_by(external_id=external_id).one_or_none()
        if report is not None:
            return report
        for report in session.query(VideoReport).all():
            raw_json = report.raw_json if isinstance(report.raw_json, dict) else {}
            if str(raw_json.get("id") or "") == external_id:
                report.external_id = external_id
                return report
        return None

    def _idea_by_external_id(self, session: Session, external_id: str) -> IdeaCard | None:
        if not external_id:
            return None
        idea = session.query(IdeaCard).filter_by(external_id=external_id).one_or_none()
        if idea is not None:
            return idea
        if external_id.startswith("idea-"):
            try:
                idea_id = int(external_id.removeprefix("idea-"))
            except ValueError:
                return None
            idea = session.get(IdeaCard, idea_id)
            if idea is not None:
                idea.external_id = external_id
            return idea
        return None

    def _create_channel(self, session: Session, channel_data: dict[str, Any]) -> Channel:
        channel = Channel(
            youtube_channel_id=str(channel_data.get("id") or channel_data.get("url") or "manual-channel"),
            title=str(channel_data.get("title") or "Untitled channel"),
            url=str(channel_data.get("url") or ""),
            description=str(channel_data.get("collection_error") or channel_data.get("description") or ""),
            status=str(channel_data.get("collection_status") or channel_data.get("status") or "active"),
        )
        session.add(channel)
        session.flush()
        return channel

    def _create_video(self, session: Session, channel: Channel, video_data: dict[str, Any]) -> Video:
        video = Video(
            channel=channel,
            youtube_video_id=str(video_data.get("youtube_video_id") or video_data.get("id") or video_data.get("url") or "manual-video"),
            title=str(video_data.get("title") or "Untitled video"),
            url=str(video_data.get("url") or ""),
            published_at=self._parse_datetime(video_data.get("published_at")),
            published_text=self._published_text(video_data),
            duration_seconds=self._as_int_or_none(video_data.get("duration_seconds")),
            view_count=self._as_int_or_none(video_data.get("view_count")),
            like_count=self._as_int_or_none(video_data.get("like_count")),
            comment_count=self._as_int_or_none(video_data.get("comment_count")),
            transcript=video_data.get("transcript"),
            transcript_status=str(video_data.get("transcript_status") or "pending"),
            analysis_status=str(video_data.get("analysis_status") or "pending"),
            is_recent_upload=bool(video_data.get("is_recent_upload")),
        )
        session.add(video)
        session.flush()
        return video

    def _create_job(self, job_data: dict[str, Any]) -> AnalysisJob:
        return AnalysisJob(
            external_id=str(job_data.get("id") or "") or None,
            type=str(job_data.get("kind") or job_data.get("type") or "video_analysis"),
            target_type=str(job_data.get("target_type") or "video_url"),
            target_id=self._as_int(job_data.get("target_id")),
            status=str(job_data.get("status") or "queued"),
            current_step=str(job_data.get("current_step") or job_data.get("status") or "queued"),
            error_message=job_data.get("error_message"),
            payload={**job_data, "external_id": job_data.get("id")},
            result_json=job_data.get("result_json"),
            started_at=self._parse_datetime(job_data.get("started_at")),
            finished_at=self._parse_datetime(job_data.get("finished_at")),
        )

    def _create_report(self, video: Video, report_data: dict[str, Any]) -> VideoReport:
        creative = report_data.get("creative_breakdown") if isinstance(report_data.get("creative_breakdown"), dict) else {}
        growth = report_data.get("growth_judgement") if isinstance(report_data.get("growth_judgement"), dict) else {}
        return VideoReport(
            external_id=str(report_data.get("id") or "") or None,
            video_id=video.id,
            summary=str(report_data.get("summary") or ""),
            topic_type=creative.get("topic_type"),
            title_hook=creative.get("title_hook"),
            opening_hook=creative.get("opening_hook"),
            structure_analysis=creative.get("structure") if isinstance(creative.get("structure"), list) else [],
            emotional_curve=creative.get("emotional_curve") if isinstance(creative.get("emotional_curve"), list) else [],
            monetization_intent=creative.get("monetization_intent"),
            growth_score=self._as_int_or_none(growth.get("score")),
            growth_judgement=growth,
            raw_json=report_data,
        )

    def _create_idea(self, video: Video, idea_data: dict[str, Any]) -> IdeaCard:
        return IdeaCard(
            external_id=str(idea_data.get("id") or "") or None,
            source_video_id=video.id,
            title=str(idea_data.get("title") or "Untitled idea"),
            angle=idea_data.get("angle"),
            why_it_works=idea_data.get("why_it_works"),
            suggested_outline=idea_data.get("outline") if isinstance(idea_data.get("outline"), list) else [],
            risk_notes=idea_data.get("risk_notes"),
            score=self._as_int_or_none(idea_data.get("score")),
            status=str(idea_data.get("status") or "saved"),
        )

    def _video_for_report(
        self,
        session: Session,
        report_data: dict[str, Any],
        default_channel: Channel | None,
        video_by_url: dict[str, Video],
        video_by_youtube_id: dict[str, Video],
    ) -> Video:
        video_url = str(report_data.get("video_url") or "")
        youtube_video_id = str(report_data.get("youtube_video_id") or "")
        if video_url and video_url in video_by_url:
            return video_by_url[video_url]
        if youtube_video_id and youtube_video_id in video_by_youtube_id:
            return video_by_youtube_id[youtube_video_id]

        channel = default_channel or self._create_channel(session, {"id": "manual-channel", "title": "Manual channel", "url": ""})
        return self._create_video(
            session,
            channel,
            {
                "youtube_video_id": youtube_video_id or video_url or f"report-video-{len(video_by_url) + 1}",
                "title": report_data.get("video_title") or "Reported video",
                "url": video_url,
                "analysis_status": "complete",
                "is_recent_upload": False,
            },
        )

    def _video_for_idea(
        self,
        default_channel: Channel | None,
        video_by_url: dict[str, Video],
        report_video_by_id: dict[str, Video],
        idea_data: dict[str, Any],
    ) -> Video | None:
        source_url = str(idea_data.get("source_video_url") or "")
        source_report_id = str(idea_data.get("source_report_id") or "")
        if source_url and source_url in video_by_url:
            return video_by_url[source_url]
        if source_report_id and source_report_id in report_video_by_id:
            return report_video_by_id[source_report_id]
        return next(iter(video_by_url.values()), None) or default_channel.videos[0] if default_channel and default_channel.videos else None

    def _channel_to_dict(self, channel: Channel) -> dict[str, Any]:
        return {
            "id": channel.youtube_channel_id,
            "title": channel.title,
            "url": channel.url,
            "subscriber_count": 0,
            "video_count": len([video for video in channel.videos if video.is_recent_upload]),
            "collection_status": channel.status,
            "collection_error": channel.description or "",
            "synced_at": self._iso(channel.updated_at),
        }

    def _video_to_dict(self, video: Video) -> dict[str, Any]:
        return {
            "id": video.youtube_video_id,
            "youtube_video_id": video.youtube_video_id,
            "title": video.title,
            "url": video.url,
            "channel_title": video.channel.title if video.channel else "",
            "channel_url": video.channel.url if video.channel else "",
            "published_at": video.published_text or (self._iso(video.published_at) if video.published_at else ""),
            "view_count": video.view_count or 0,
            "analysis_status": video.analysis_status,
        }

    def _job_to_dict(self, job: AnalysisJob) -> dict[str, Any]:
        payload = job.payload if isinstance(job.payload, dict) else {}
        return {
            **payload,
            "id": str(job.external_id or payload.get("external_id") or f"job-{job.id}"),
            "kind": job.type,
            "status": job.status,
            "current_step": job.current_step,
            "target_url": payload.get("target_url") or payload.get("video_url") or "",
            "error_message": job.error_message or payload.get("error_message") or "",
            "created_at": self._iso(job.created_at),
            "updated_at": self._iso(job.updated_at),
        }

    def _report_to_dict(self, report: VideoReport) -> dict[str, Any]:
        if isinstance(report.raw_json, dict) and report.raw_json:
            return {
                **report.raw_json,
                "id": report.external_id or report.raw_json.get("id") or f"report-{report.id}",
            }
        video = report.video
        return {
            "id": report.external_id or f"report-{report.id}",
            "youtube_video_id": video.youtube_video_id if video else "",
            "video_url": video.url if video else "",
            "video_title": video.title if video else "",
            "channel_title": video.channel.title if video and video.channel else "",
            "summary": report.summary,
            "creative_breakdown": {
                "topic_type": report.topic_type or "",
                "title_hook": report.title_hook or "",
                "opening_hook": report.opening_hook or "",
                "structure": report.structure_analysis or [],
                "emotional_curve": report.emotional_curve or [],
                "monetization_intent": report.monetization_intent,
            },
            "growth_judgement": report.growth_judgement or {"score": report.growth_score or 0, "reasons": []},
            "idea_cards": [],
            "comment_insights": {"status": "not_configured"},
            "collection_evidence": {},
            "created_at": self._iso(report.created_at),
        }

    def _idea_to_dict(self, idea: IdeaCard) -> dict[str, Any]:
        video = idea.source_video
        report = video.reports[0] if video and video.reports else None
        report_id = ""
        if report and isinstance(report.raw_json, dict):
            report_id = str(report.raw_json.get("id") or "")
        return {
            "id": idea.external_id or f"idea-{idea.id}",
            "source": video.title if video else "",
            "source_video_url": video.url if video else "",
            "source_report_id": report_id,
            "title": idea.title,
            "angle": idea.angle or "",
            "why_it_works": idea.why_it_works or "",
            "outline": idea.suggested_outline or [],
            "risk_notes": idea.risk_notes or "",
            "score": idea.score or 0,
            "status": idea.status,
        }

    def _as_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _as_int_or_none(self, value: Any) -> int | None:
        if value in {None, ""}:
            return None
        return self._as_int(value)

    def _parse_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    def _published_text(self, video_data: dict[str, Any]) -> str:
        raw_text = video_data.get("published_text") or video_data.get("published_at") or ""
        if isinstance(raw_text, datetime):
            return raw_text.isoformat()
        return str(raw_text)

    def _iso(self, value: datetime | None) -> str:
        if value is None:
            return datetime.now(UTC).isoformat()
        return value.isoformat()
