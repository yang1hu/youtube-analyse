from fastapi import APIRouter
from pydantic import BaseModel

from creator_agent.config import Settings

router = APIRouter(prefix="/api")


class AnalyzeVideoRequest(BaseModel):
    video_url: str


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": Settings().app_name}


@router.get("/dashboard")
def dashboard() -> dict:
    return {
        "channels": [],
        "recent_videos": [],
        "idea_cards": [],
        "jobs": [],
        "comment_collector_status": "not_configured",
    }


@router.post("/analysis/video")
def create_video_analysis(request: AnalyzeVideoRequest) -> dict:
    return {"status": "queued", "target_type": "video_url", "video_url": request.video_url}
