import pytest

from creator_agent.db.models import AnalysisJob
from creator_agent.jobs.pipeline import create_analysis_job
from creator_agent.jobs.worker import run_analysis_job


def test_create_analysis_job_records_manual_video_url(db_session):
    job = create_analysis_job(
        db_session,
        target_type="video_url",
        target_id=0,
        payload={"video_url": "https://youtu.be/abc123"},
    )

    saved = db_session.get(AnalysisJob, job.id)
    assert saved.status == "queued"
    assert saved.type == "video_analysis"
    assert saved.current_step == "queued"


def test_run_analysis_job_completes_video_analysis(db_session):
    job = create_analysis_job(
        db_session,
        target_type="video_url",
        target_id=0,
        payload={"video_url": "https://youtu.be/abc123"},
    )

    video_id = run_analysis_job(db_session, job.id)

    saved = db_session.get(AnalysisJob, job.id)
    assert video_id > 0
    assert saved.status == "complete"
    assert saved.current_step == "complete"
    assert saved.target_type == "video"
    assert saved.target_id == video_id


def test_run_analysis_job_missing_job_raises_value_error(db_session):
    with pytest.raises(ValueError, match="AnalysisJob 999 not found"):
        run_analysis_job(db_session, 999)


def test_run_analysis_job_failure_marks_job_failed(db_session):
    job = create_analysis_job(
        db_session,
        target_type="video_url",
        target_id=0,
        payload={},
    )

    with pytest.raises(KeyError, match="video_url"):
        run_analysis_job(db_session, job.id)

    saved = db_session.get(AnalysisJob, job.id)
    assert saved.status == "failed"
    assert saved.current_step == "failed"
    assert "video_url" in saved.error_message
    assert saved.finished_at is not None
