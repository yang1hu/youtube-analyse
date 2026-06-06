from typing import Any

from sqlalchemy.orm import Session

from creator_agent.db.models import AnalysisJob


def create_analysis_job(
    db_session: Session,
    target_type: str,
    target_id: int,
    payload: dict[str, Any],
) -> AnalysisJob:
    job = AnalysisJob(
        type="video_analysis",
        target_type=target_type,
        target_id=target_id,
        status="queued",
        current_step="queued",
        payload=payload,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job
