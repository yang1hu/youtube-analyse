import pytest
from pydantic import ValidationError

from creator_agent.agent.schemas import CommentInsights, CreatorReport, IdeaCardArtifact


def test_creator_report_accepts_not_configured_comments():
    report = CreatorReport(
        summary="A video about creator growth.",
        creative_breakdown={
            "topic_type": "creator_growth",
            "title_hook": "clear outcome",
            "opening_hook": "pain point",
            "structure": ["promise", "framework"],
            "emotional_curve": ["curiosity", "confidence"],
            "monetization_intent": "newsletter",
        },
        growth_judgement={"score": 80, "reasons": ["clear audience promise"]},
        idea_cards=[
            IdeaCardArtifact(
                title="I tested this growth loop",
                angle="experiment",
                why_it_works="Concrete experiment beats abstract advice.",
                outline=["setup", "test", "results"],
                risk_notes="Avoid copying the source title.",
                score=75,
            )
        ],
        comment_insights=CommentInsights(status="not_configured"),
    )

    assert report.comment_insights.status == "not_configured"
    assert report.idea_cards[0].score == 75


def test_idea_card_score_must_be_between_zero_and_one_hundred():
    with pytest.raises(ValidationError):
        IdeaCardArtifact(
            title="Bad score",
            angle="test",
            why_it_works="Score is invalid.",
            outline=["one"],
            risk_notes="none",
            score=101,
        )


from creator_agent.agent.runtime import AgentRuntime
from creator_agent.tools import build_default_registry


def test_agent_runtime_generates_creator_growth_report():
    runtime = AgentRuntime(tool_registry=build_default_registry())

    result = runtime.run_video_analysis(video_url="https://youtu.be/abc123")

    assert result.report.summary
    assert result.report.creative_breakdown.topic_type == "creator_growth"
    assert result.report.comment_insights.status == "not_configured"
    assert result.report.idea_cards[0].score >= 0
    assert result.tool_results["get_comments"]["status"] == "not_configured"


from creator_agent.db.models import IdeaCard, VideoReport
from creator_agent.services.analysis_service import AnalysisService


def test_analysis_service_persists_report_and_idea_cards(db_session):
    service = AnalysisService(db_session=db_session, runtime=AgentRuntime(build_default_registry()))

    video = service.analyze_video_url("https://youtu.be/abc123")

    report = db_session.query(VideoReport).filter_by(video_id=video.id).one()
    ideas = db_session.query(IdeaCard).filter_by(source_video_id=video.id).all()
    assert report.topic_type == "creator_growth"
    assert report.growth_score >= 0
    assert len(ideas) == 1
