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
from creator_agent.agent.schemas import CommentInsights, CreatorReport, CreativeBreakdown, GrowthJudgement, IdeaCardArtifact
from creator_agent.tools import build_default_registry
from creator_agent.tools.registry import ToolRegistry


def test_agent_runtime_generates_video_breakdown_report(monkeypatch):
    monkeypatch.setattr(
        "creator_agent.agent.runtime.LLMReportAnalyzer.analyze",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("LLM disabled in this test")),
    )
    monkeypatch.setattr(
        "creator_agent.tools.youtube_metadata.collect_video_metadata",
        lambda video_url=None, video_id=None: {
            "youtube_video_id": video_id or "abc123",
            "title": "A practical video packaging breakdown",
            "url": video_url,
            "channel": {"id": "UC123", "title": "Packaging Lab", "url": "https://www.youtube.com/@packaginglab"},
            "view_count": 1000,
            "like_count": 0,
            "comment_count": 0,
            "collection_status": "ok",
            "collection_source": "test",
        },
    )
    monkeypatch.setattr(
        "creator_agent.tools.transcript.collect_video_content",
        lambda video_id: {
            "status": "ready",
            "video_id": video_id,
            "transcript_text": "This video opens with a clear promise. Then it explains the conflict. Finally it gives a practical takeaway.",
            "transcript_source": "test_caption",
            "language": "en",
            "description": "Packaging analysis.",
            "collection_source": "test",
        },
    )
    runtime = AgentRuntime(tool_registry=build_default_registry())

    result = runtime.run_video_analysis(video_url="https://youtu.be/abc123")

    assert result.report.summary
    assert result.report.creative_breakdown.topic_type == "video_breakdown"
    assert result.report.comment_insights.status == "not_configured"
    assert result.report.idea_cards[0].score >= 0
    assert result.tool_results["get_comments"]["status"] == "not_configured"


def test_agent_runtime_classifies_story_recap_from_title_and_transcript(monkeypatch):
    monkeypatch.setattr(
        "creator_agent.agent.runtime.LLMReportAnalyzer.analyze",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("LLM disabled in this test")),
    )
    registry = ToolRegistry()
    registry.register(
        "get_video_metadata",
        "metadata",
        lambda video_url: {
            "youtube_video_id": "abc123",
            "title": "After HEARING My Thoughts, The Ice QUEEN Billionaire REFUSED to Let Me Leave - Manhwa Recap",
            "url": video_url,
            "channel": {"id": "UC123", "title": "Sam's Diary", "url": "https://www.youtube.com/@SamsDiary-v5f"},
            "view_count": 81000,
            "like_count": 0,
            "comment_count": 0,
        },
    )
    registry.register(
        "get_transcript",
        "transcript",
        lambda video_id: {
            "status": "ready",
            "video_id": video_id,
            "text": "She could hear every thought he tried to hide. The billionaire refused to let him leave. Then the story turned into a contract marriage conflict.",
            "source": "yt-dlp_auto_subtitle",
            "description": "A manhwa recap about romance, mind reading, and power.",
        },
    )
    registry.register("get_comments", "comments", lambda video_id, mode, limit: {"status": "not_configured"})
    registry.register(
        "get_channel_profile",
        "profile",
        lambda channel_id, channel_url: {"description": "Manhwa recap stories"},
    )
    registry.register(
        "compute_video_metrics",
        "metrics",
        lambda video, channel_baseline: {"performance_band": "high"},
    )

    result = AgentRuntime(tool_registry=registry).run_video_analysis("https://www.youtube.com/watch?v=abc123")

    assert result.report.creative_breakdown.topic_type == "story_recap"
    assert result.report.creative_breakdown.structure[0].startswith("Premise:")
    assert any(item.startswith("Central conflict:") for item in result.report.creative_breakdown.structure)
    assert result.report.idea_cards[0].angle == "story recap packaging"
    assert "fantasy conflict" in result.report.idea_cards[0].why_it_works
    assert len(result.report.idea_cards[0].outline) >= 6
    assert any("Opening hook" in item for item in result.report.idea_cards[0].outline)
    assert any("Ending suspense" in item for item in result.report.idea_cards[0].outline)


def test_agent_runtime_prefers_llm_report_when_available(monkeypatch):
    registry = ToolRegistry()
    registry.register(
        "get_video_metadata",
        "metadata",
        lambda video_url: {
            "youtube_video_id": "abc123",
            "title": "Story recap",
            "url": video_url,
            "channel": {"id": "UC123", "title": "Sam's Diary", "url": "https://www.youtube.com/@sam"},
            "view_count": 1000,
        },
    )
    registry.register(
        "get_transcript",
        "transcript",
        lambda video_id: {"status": "ready", "video_id": video_id, "text": "A long story script.", "source": "test"},
    )
    registry.register("get_comments", "comments", lambda video_id, mode, limit: {"status": "not_configured"})
    registry.register("get_channel_profile", "profile", lambda channel_id, channel_url: {"description": ""})
    registry.register("compute_video_metrics", "metrics", lambda video, channel_baseline: {"performance_band": "normal"})

    def fake_analyze(self, metadata, transcript, comments, channel_profile, metrics):
        return CreatorReport(
            summary="LLM 抓到了真正重点。",
            creative_breakdown=CreativeBreakdown(
                topic_type="llm_story_recap",
                title_hook="LLM title hook",
                opening_hook="LLM opening hook",
                structure=["LLM beat"],
                emotional_curve=["LLM curve"],
            ),
            growth_judgement=GrowthJudgement(score=88, reasons=["LLM reason"]),
            idea_cards=[
                IdeaCardArtifact(
                    title="LLM idea",
                    angle="LLM angle",
                    why_it_works="LLM why",
                    outline=["LLM outline"],
                    risk_notes="LLM risk",
                    score=88,
                )
            ],
            comment_insights=CommentInsights(status="not_configured"),
        )

    monkeypatch.setattr("creator_agent.agent.runtime.LLMReportAnalyzer.analyze", fake_analyze)

    result = AgentRuntime(tool_registry=registry).run_video_analysis("https://www.youtube.com/watch?v=abc123")

    assert result.report.summary == "LLM 抓到了真正重点。"
    assert result.report.creative_breakdown.topic_type == "llm_story_recap"
    assert result.tool_results["analyze_with_llm"]["status"] == "ok"


from creator_agent.db.models import IdeaCard, VideoReport
from creator_agent.services.analysis_service import AnalysisService


def test_analysis_service_persists_report_and_idea_cards(db_session, monkeypatch):
    monkeypatch.setattr(
        "creator_agent.agent.runtime.LLMReportAnalyzer.analyze",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("LLM disabled in this test")),
    )
    monkeypatch.setattr(
        "creator_agent.tools.youtube_metadata.collect_video_metadata",
        lambda video_url=None, video_id=None: {
            "youtube_video_id": video_id or "abc123",
            "title": "A practical video packaging breakdown",
            "url": video_url,
            "channel": {"id": "UC123", "title": "Packaging Lab", "url": "https://www.youtube.com/@packaginglab"},
            "view_count": 1000,
            "like_count": 0,
            "comment_count": 0,
            "collection_status": "ok",
            "collection_source": "test",
        },
    )
    monkeypatch.setattr(
        "creator_agent.tools.transcript.collect_video_content",
        lambda video_id: {
            "status": "ready",
            "video_id": video_id,
            "transcript_text": "This video opens with a clear promise. Then it explains the conflict. Finally it gives a practical takeaway.",
            "transcript_source": "test_caption",
            "language": "en",
            "description": "Packaging analysis.",
            "collection_source": "test",
        },
    )
    service = AnalysisService(db_session=db_session, runtime=AgentRuntime(build_default_registry()))

    video = service.analyze_video_url("https://youtu.be/abc123")

    report = db_session.query(VideoReport).filter_by(video_id=video.id).one()
    ideas = db_session.query(IdeaCard).filter_by(source_video_id=video.id).all()
    assert report.topic_type == "video_breakdown"
    assert report.growth_score >= 0
    assert len(ideas) == 1
