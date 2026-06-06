from datetime import UTC, datetime

from sqlalchemy.orm import Session

from creator_agent.agent.runtime import AgentRuntime
from creator_agent.db.models import AnalysisJob
from creator_agent.services.analysis_service import AnalysisService
from creator_agent.tools import build_default_registry


def run_analysis_job(db_session: Session, job_id: int) -> int:
    job = db_session.get(AnalysisJob, job_id)
    if job is None:
        raise ValueError(f"AnalysisJob {job_id} not found.")

    job.status = "running"
    job.current_step = "analysis"
    job.started_at = datetime.now(UTC)
    db_session.commit()

    try:
        runtime = AgentRuntime(build_default_registry())
        service = AnalysisService(db_session=db_session, runtime=runtime)
        video = service.analyze_video_url(job.payload["video_url"])

        job.status = "complete"
        job.current_step = "complete"
        job.target_type = "video"
        job.target_id = video.id
        job.finished_at = datetime.now(UTC)
        db_session.commit()
        return video.id
    except Exception as exc:
        job.status = "failed"
        job.current_step = "failed"
        job.error_message = str(exc)
        job.finished_at = datetime.now(UTC)
        db_session.commit()
        raise
