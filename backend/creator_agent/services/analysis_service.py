from sqlalchemy.orm import Session

from creator_agent.agent.runtime import AgentRuntime
from creator_agent.db.models import IdeaCard, Video, VideoReport
from creator_agent.db.repositories import ChannelRepository, VideoRepository


class AnalysisService:
    def __init__(self, db_session: Session, runtime: AgentRuntime) -> None:
        self.db_session = db_session
        self.runtime = runtime

    def analyze_video_url(self, video_url: str) -> Video:
        result = self.runtime.run_video_analysis(video_url)
        metadata = result.tool_results["get_video_metadata"]
        report = result.report

        channel_metadata = metadata.get("channel") if isinstance(metadata.get("channel"), dict) else {}
        youtube_channel_id = str(
            channel_metadata.get("youtube_channel_id")
            or channel_metadata.get("id")
            or metadata.get("channel_id")
            or ""
        )
        channel = ChannelRepository(self.db_session).get_or_create(
            youtube_channel_id=youtube_channel_id,
            title=str(channel_metadata.get("title") or "Untitled channel"),
            url=str(channel_metadata.get("url") or f"https://www.youtube.com/channel/{youtube_channel_id}"),
        )

        video = VideoRepository(self.db_session).get_or_create(channel=channel, metadata=metadata)

        existing_report = self.db_session.query(VideoReport).filter_by(video_id=video.id).one_or_none()
        if existing_report is not None:
            self.db_session.delete(existing_report)

        for idea in self.db_session.query(IdeaCard).filter_by(source_video_id=video.id).all():
            self.db_session.delete(idea)

        self.db_session.flush()

        creative_breakdown = report.creative_breakdown
        growth_judgement = report.growth_judgement
        self.db_session.add(
            VideoReport(
                video_id=video.id,
                summary=report.summary,
                topic_type=creative_breakdown.topic_type,
                title_hook=creative_breakdown.title_hook,
                opening_hook=creative_breakdown.opening_hook,
                structure_analysis=creative_breakdown.structure,
                emotional_curve=creative_breakdown.emotional_curve,
                monetization_intent=creative_breakdown.monetization_intent,
                growth_score=growth_judgement.score,
                growth_judgement=growth_judgement.model_dump(),
                raw_json=report.model_dump(),
            )
        )

        for idea_card in report.idea_cards:
            self.db_session.add(
                IdeaCard(
                    source_video_id=video.id,
                    title=idea_card.title,
                    angle=idea_card.angle,
                    why_it_works=idea_card.why_it_works,
                    suggested_outline=idea_card.outline,
                    risk_notes=idea_card.risk_notes,
                    score=idea_card.score,
                    status="saved",
                )
            )

        video.analysis_status = "complete"
        self.db_session.commit()
        return video
