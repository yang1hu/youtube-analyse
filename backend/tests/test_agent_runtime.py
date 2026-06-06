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
