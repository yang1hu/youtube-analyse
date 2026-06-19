from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from creator_agent.config import Settings
from creator_agent.services.cache_service import CacheService
from creator_agent.services.health_check_service import HealthCheckService
from creator_agent.services.imitation_factory_service import ImitationFactoryService
from creator_agent.services.monitor_service import MonitorService
from creator_agent.services.sample_library_service import SampleLibraryService
from creator_agent.services.script_studio_service import ScriptStudioService
from creator_agent.services.settings_service import WorkspaceSettings, WorkspaceSettingsService
from creator_agent.services.style_service import StyleService
from creator_agent.services.task_service import TaskService
from creator_agent.services.transcript_store import TranscriptStore
from creator_agent.services.translation_service import TranslationService
from creator_agent.services.workspace_store import WorkspaceStore

router = APIRouter(prefix="/api")


class AnalyzeVideoRequest(BaseModel):
    video_url: str


class AnalyzeSampleRequest(BaseModel):
    video_url: str
    video_title: str | None = ""
    video_id: str | None = ""


class UpdateSampleRequest(BaseModel):
    favorite: bool | None = None
    tags: list[str] | None = None
    notes: str | None = None


class MergeSamplesRequest(BaseModel):
    sample_ids: list[str]
    name: str = "Merged sample style"


class TranslateRequest(BaseModel):
    force: bool = False


class ClearCacheRequest(BaseModel):
    target: str = "samples"


class GenerateScriptRequest(BaseModel):
    idea_id: str
    style_id: str | None = None


class RewriteScriptRequest(BaseModel):
    style_id: str | None = None


class UpdateScriptRequest(BaseModel):
    selected_title: str | None = None
    opening_30s: str | None = None
    full_script: str | None = None


class LearnStyleRequest(BaseModel):
    name: str | None = None


class ApplyStyleRequest(BaseModel):
    style_id: str
    idea_id: str
    draft_type: str = "opening_script"


class CreateImitationRequest(BaseModel):
    report_id: str
    idea_id: str | None = None
    direction: str
    output_type: str = "short_fiction"
    similarity_level: str = "medium"
    target_length: str = "2500-4000 Chinese characters"
    keep_narration: bool = True


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": Settings().app_name}


@router.get("/health/checks")
def health_checks() -> dict:
    return HealthCheckService().run_checks()


@router.get("/dashboard")
def dashboard() -> dict:
    return WorkspaceStore().dashboard()


@router.get("/tasks")
def tasks() -> dict:
    return TaskService().list_tasks()


@router.get("/monitor")
def monitor_status() -> dict:
    return MonitorService().status()


@router.post("/monitor/run")
def run_monitor() -> dict:
    try:
        return MonitorService().run_once()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/tasks/channel-sync/start")
def start_channel_sync_task() -> dict:
    return TaskService().create_task("channel_sync", {})


@router.post("/tasks/video-analysis/start")
def start_video_analysis_task(request: AnalyzeVideoRequest) -> dict:
    return TaskService().create_task("video_analysis", {"video_url": request.video_url})


@router.post("/tasks/sample-analysis/start")
def start_sample_analysis_task(request: AnalyzeSampleRequest) -> dict:
    return TaskService().create_task(
        "sample_analysis",
        {
            "video_url": request.video_url,
            "video_title": request.video_title or "",
            "video_id": request.video_id or "",
        },
    )


@router.post("/tasks/reports/{report_id}/translation/start")
def start_report_translation_task(report_id: str, request: TranslateRequest) -> dict:
    report = WorkspaceStore().report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    video_id = str(report.get("youtube_video_id") or "")
    if not video_id:
        raise HTTPException(status_code=404, detail="No transcript is linked to this report.")

    return TaskService().create_task(
        "translation",
        {
            "video_id": video_id,
            "target_language": "zh-CN",
            "force": request.force,
            "target_url": str(report.get("video_url") or ""),
            "report_id": report_id,
        },
    )


@router.post("/tasks/{task_id}/retry")
def retry_task(task_id: str) -> dict:
    try:
        return TaskService().retry_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/run")
def run_task(task_id: str) -> dict:
    try:
        return TaskService().run_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/tasks/worker/run-next")
def run_next_queued_task() -> dict:
    try:
        return TaskService().run_next_queued_task()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/analysis/video")
def create_video_analysis(request: AnalyzeVideoRequest) -> dict:
    return WorkspaceStore().analyze_video(request.video_url)


@router.get("/cache")
def cache_info() -> dict:
    return CacheService().info()


@router.post("/cache/clear")
def clear_cache(request: ClearCacheRequest) -> dict:
    if request.target not in {"samples", "transcripts", "translations", "all"}:
        raise HTTPException(status_code=422, detail="Unknown cache target.")
    return CacheService().clear(request.target)  # type: ignore[arg-type]


@router.get("/samples")
def sample_analyses() -> dict:
    return {"sample_analyses": WorkspaceStore().sample_analyses()}


@router.get("/samples/library")
def sample_library() -> dict:
    return SampleLibraryService().list_samples()


@router.post("/samples/merge-style")
def merge_samples_into_style(request: MergeSamplesRequest) -> dict:
    try:
        return SampleLibraryService().merge_style(request.sample_ids, request.name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/samples/analyze")
def create_sample_analysis(request: AnalyzeSampleRequest) -> dict:
    try:
        result = WorkspaceStore().create_sample_analysis(
            video_url=request.video_url,
            video_title=request.video_title or "",
            video_id=request.video_id or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"sample_analysis": result}


@router.patch("/samples/{sample_id}")
def update_sample(sample_id: str, request: UpdateSampleRequest) -> dict:
    try:
        return SampleLibraryService().update_sample(sample_id, request.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/reports/latest/reanalyze")
def reanalyze_latest_report() -> dict:
    report = WorkspaceStore().latest_report()
    if not report:
        raise HTTPException(status_code=404, detail="No report is available.")

    video_url = str(report.get("video_url") or "")
    if not video_url:
        raise HTTPException(status_code=404, detail="No video URL is linked to the latest report.")

    return WorkspaceStore().analyze_video(video_url)


@router.post("/channel/sync")
def sync_channel() -> dict:
    try:
        return WorkspaceStore().sync_channel()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/settings", response_model=WorkspaceSettings)
def get_settings() -> WorkspaceSettings:
    return WorkspaceSettingsService().get()


@router.put("/settings", response_model=WorkspaceSettings)
def update_settings(workspace_settings: WorkspaceSettings) -> WorkspaceSettings:
    return WorkspaceSettingsService().save(workspace_settings)


@router.get("/reports/latest")
def latest_report() -> dict:
    report = WorkspaceStore().latest_report()
    return {"report": report}


@router.get("/reports")
def reports() -> dict:
    return {"reports": WorkspaceStore().reports()}


@router.get("/reports/{report_id}")
def report_detail(report_id: str) -> dict:
    report = WorkspaceStore().report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    return {"report": report}


@router.get("/reports/latest/transcript")
def latest_report_transcript() -> dict:
    report = WorkspaceStore().latest_report()
    if not report:
        return {"transcript": None, "translation": None}

    video_id = str(report.get("youtube_video_id") or "")
    if not video_id:
        return {"transcript": None, "translation": None}

    store = TranscriptStore()
    return {
        "transcript": store.get_transcript(video_id),
        "translation": store.get_translation(video_id, target_language="zh-CN"),
        "translation_status": store.get_translation_status(video_id, target_language="zh-CN"),
    }


@router.get("/reports/{report_id}/transcript")
def report_transcript(report_id: str) -> dict:
    report = WorkspaceStore().report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    video_id = str(report.get("youtube_video_id") or "")
    if not video_id:
        return {"transcript": None, "translation": None}

    store = TranscriptStore()
    return {
        "transcript": store.get_transcript(video_id),
        "translation": store.get_translation(video_id, target_language="zh-CN"),
        "translation_status": store.get_translation_status(video_id, target_language="zh-CN"),
    }


@router.post("/reports/latest/translate")
def translate_latest_report(request: TranslateRequest) -> dict:
    report = WorkspaceStore().latest_report()
    if not report:
        raise HTTPException(status_code=404, detail="No report is available.")

    video_id = str(report.get("youtube_video_id") or "")
    if not video_id:
        raise HTTPException(status_code=404, detail="No transcript is linked to the latest report.")

    try:
        result = TranslationService().start_background_translation(
            video_id,
            target_language="zh-CN",
            force=request.force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return result


@router.post("/reports/{report_id}/translate")
def translate_report(report_id: str, request: TranslateRequest) -> dict:
    report = WorkspaceStore().report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    video_id = str(report.get("youtube_video_id") or "")
    if not video_id:
        raise HTTPException(status_code=404, detail="No transcript is linked to this report.")

    try:
        result = TranslationService().start_background_translation(
            video_id,
            target_language="zh-CN",
            force=request.force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return result


@router.get("/ideas")
def ideas() -> dict:
    return {"idea_cards": WorkspaceStore().ideas()}


@router.post("/ideas/prune-stale")
def prune_stale_ideas() -> dict:
    return WorkspaceStore().prune_stale_ideas()


@router.get("/scripts")
def scripts() -> dict:
    return ScriptStudioService().list_scripts()


@router.post("/scripts/generate")
def generate_script(request: GenerateScriptRequest) -> dict:
    try:
        return ScriptStudioService().generate_script(request.idea_id, request.style_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/scripts/{script_id}/rewrite")
def rewrite_script(script_id: str, request: RewriteScriptRequest) -> dict:
    try:
        return ScriptStudioService().rewrite_script(script_id, request.style_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/scripts/{script_id}")
def update_script(script_id: str, request: UpdateScriptRequest) -> dict:
    try:
        return ScriptStudioService().update_script(
            script_id,
            selected_title=request.selected_title,
            opening_30s=request.opening_30s,
            full_script=request.full_script,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/scripts/{script_id}/markdown")
def export_script_markdown(script_id: str) -> dict:
    try:
        return ScriptStudioService().export_markdown(script_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/styles")
def styles() -> dict:
    return StyleService().list_styles()


@router.post("/styles/learn-latest")
def learn_latest_style(request: LearnStyleRequest) -> dict:
    try:
        return StyleService().learn_from_latest_report(name=request.name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/styles/apply")
def apply_style(request: ApplyStyleRequest) -> dict:
    try:
        return StyleService().apply_style(
            style_id=request.style_id,
            idea_id=request.idea_id,
            draft_type=request.draft_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/imitation-factory")
def imitation_factory() -> dict:
    return ImitationFactoryService().list_projects()


@router.post("/imitation-factory/projects")
def create_imitation_project(request: CreateImitationRequest) -> dict:
    if request.similarity_level not in {"low", "medium", "high"}:
        raise HTTPException(status_code=422, detail="Unknown similarity level.")
    if request.output_type not in {"short_fiction", "story_recap", "short_drama", "interactive"}:
        raise HTTPException(status_code=422, detail="Unknown output type.")
    if not request.direction.strip():
        raise HTTPException(status_code=422, detail="Direction is required.")
    try:
        return ImitationFactoryService().create_project(
            report_id=request.report_id,
            idea_id=request.idea_id,
            direction=request.direction,
            output_type=request.output_type,
            similarity_level=request.similarity_level,
            target_length=request.target_length,
            keep_narration=request.keep_narration,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/imitation-factory/projects/{project_id}/markdown")
def export_imitation_markdown(project_id: str) -> dict:
    try:
        return ImitationFactoryService().export_markdown(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
