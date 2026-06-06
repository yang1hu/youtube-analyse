from creator_agent.config import Settings
from datetime import UTC, datetime

from creator_agent.db.models import AnalysisJob, Channel, IdeaCard, Video, VideoReport


def test_settings_defaults_are_mysql_and_redis_ready():
    settings = Settings()

    assert settings.database_url.startswith("mysql+pymysql://")
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.app_name == "YouTube Creator Growth Agent"


def test_channel_video_report_and_idea_card_persist(db_session):
    channel = Channel(
        youtube_channel_id="UC123",
        title="Growth Lab",
        url="https://youtube.com/@growthlab",
        status="active",
    )
    db_session.add(channel)
    db_session.flush()

    video = Video(
        channel_id=channel.id,
        youtube_video_id="abc123",
        title="How creators grow fast",
        url="https://youtu.be/abc123",
        published_at=datetime(2026, 6, 6, tzinfo=UTC),
        duration_seconds=900,
        view_count=10000,
        like_count=700,
        comment_count=120,
        transcript_status="ready",
        analysis_status="pending",
    )
    db_session.add(video)
    db_session.flush()

    report = VideoReport(
        video_id=video.id,
        summary="A practical breakdown of creator growth loops.",
        topic_type="creator_growth",
        title_hook="specific outcome",
        opening_hook="pain-first",
        structure_analysis=["promise", "framework", "examples"],
        emotional_curve=["curiosity", "tension", "confidence"],
        monetization_intent="course funnel",
        growth_score=82,
        growth_judgement={"reasons": ["clear promise"]},
        raw_json={"summary": "A practical breakdown of creator growth loops."},
    )
    db_session.add(report)

    idea = IdeaCard(
        source_video_id=video.id,
        title="I copied a creator growth loop for 7 days",
        angle="experiment",
        why_it_works="It turns an abstract framework into a concrete challenge.",
        suggested_outline=["setup", "execution", "results"],
        risk_notes="Avoid implying guaranteed results.",
        score=78,
        status="saved",
    )
    db_session.add(idea)
    db_session.commit()

    saved = db_session.get(VideoReport, report.id)

    assert saved.video.youtube_video_id == "abc123"
    assert saved.structure_analysis == ["promise", "framework", "examples"]
    assert saved.video.idea_cards[0].status == "saved"


def test_analysis_job_tracks_current_step(db_session):
    job = AnalysisJob(type="video_analysis", target_type="video", target_id=42, status="queued")

    db_session.add(job)
    db_session.commit()

    saved = db_session.get(AnalysisJob, job.id)

    assert saved.status == "queued"
    assert saved.current_step == "queued"
