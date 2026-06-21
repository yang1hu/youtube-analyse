from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from creator_agent.config import Settings
from creator_agent.services.cache_service import CacheService
from creator_agent.services.health_check_service import HealthCheckService
from creator_agent.services.imitation_factory_service import ImitationFactoryService, InkOSRunError
from creator_agent.services.monitor_service import MonitorService
from creator_agent.services.sample_library_service import SampleLibraryService
from creator_agent.services.script_studio_service import ScriptStudioService
from creator_agent.services.settings_service import WorkspaceSettings, WorkspaceSettingsService
from creator_agent.services.story_workbench_service import StoryWorkbenchService
from creator_agent.services.style_service import StyleService
from creator_agent.services.task_service import TaskService
from creator_agent.services.transcript_store import TranscriptStore
from creator_agent.services.translation_service import TranslationService
from creator_agent.services.workspace_store import WorkspaceStore

router = APIRouter(prefix="/api")


class AnalyzeVideoRequest(BaseModel):
    video_url: str


class BatchAnalyzeVideosRequest(BaseModel):
    limit: int = 10
    prioritize_candidates: bool = False
    video_urls: list[str] | None = None


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


class MergeReportStylesRequest(BaseModel):
    report_ids: list[str]
    name: str | None = None


class ApplyStyleRequest(BaseModel):
    style_id: str
    idea_id: str
    draft_type: str = "opening_script"


class CreateImitationRequest(BaseModel):
    report_id: str
    idea_id: str | None = None
    template_id: str | None = None
    style_id: str | None = None
    direction: str
    output_type: str = "short_fiction"
    similarity_level: str = "medium"
    target_length: str = "2500-4000 Chinese characters"
    keep_narration: bool = True


class SaveImitationDraftRequest(BaseModel):
    draft_text: str
    title: str | None = ""


class RunImitationInkosRequest(BaseModel):
    reference_run_id: str | None = None


class UpdateImitationDraftRequest(BaseModel):
    status: str


class BulkProjectStatusRequest(BaseModel):
    project_ids: list[str]
    status: str


class BulkProjectExportRequest(BaseModel):
    project_ids: list[str]
    include_reference: bool = True
    include_latest_draft: bool = True


class BulkProjectCheckRequest(BaseModel):
    project_ids: list[str]


class BulkProjectInkosRequest(BaseModel):
    project_ids: list[str]
    skip_publishable: bool = True


class UpdateStructureTemplateRequest(BaseModel):
    name: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    applicable_topics: list[str] | None = None
    success_cases: list[str] | None = None


class RewriteImitationDraftRequest(BaseModel):
    mode: str


class RewriteRiskSegmentRequest(BaseModel):
    segment_index: int


class SaveStoryWorkbenchRequest(BaseModel):
    cleaned_text: str


class UpdateStoryAnalysisRequest(BaseModel):
    opening_5s_hook: str | None = None
    first_30s_retention: str | None = None
    protagonist_position: str | None = None
    status_gap: str | None = None
    first_payoff: str | None = None
    middle_escalation: str | None = None
    opposition_design: str | None = None
    public_reversal: str | None = None
    ending_suspense: str | None = None
    reusable_template: list[str] | None = None
    non_reusable_content: list[str] | None = None
    structure_confidence: str | None = None


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": Settings().app_name}


@router.get("/health/checks")
def health_checks() -> dict:
    return HealthCheckService().run_checks()


@router.get("/dashboard")
def dashboard() -> dict:
    return WorkspaceStore().dashboard()


@router.post("/dashboard/demo")
def load_demo_workspace() -> dict:
    return WorkspaceStore().load_demo_workspace()


@router.post("/projects/{project_id}/favorite-template")
def favorite_project_structure_template(project_id: str) -> dict:
    try:
        return WorkspaceStore().save_favorite_structure_template(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/projects/{project_id}/favorite-template")
def unfavorite_project_structure_template(project_id: str) -> dict:
    return WorkspaceStore().delete_favorite_structure_template(project_id)


@router.post("/projects/bulk-status")
def bulk_update_project_latest_draft_status(request: BulkProjectStatusRequest) -> dict:
    try:
        return ImitationFactoryService().bulk_update_latest_draft_status(request.project_ids, request.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/bulk-markdown")
def bulk_export_project_markdown(request: BulkProjectExportRequest) -> dict:
    try:
        return ImitationFactoryService().bulk_export_markdown(
            request.project_ids,
            include_reference=request.include_reference,
            include_latest_draft=request.include_latest_draft,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/bulk-check")
def bulk_check_project_latest_drafts(request: BulkProjectCheckRequest) -> dict:
    try:
        return ImitationFactoryService().bulk_check_latest_drafts(request.project_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects/bulk-inkos")
def bulk_run_project_inkos(request: BulkProjectInkosRequest) -> dict:
    try:
        return ImitationFactoryService().bulk_run_inkos(
            request.project_ids,
            skip_publishable=request.skip_publishable,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/projects/templates/{template_id}")
def update_structure_template(template_id: str, request: UpdateStructureTemplateRequest) -> dict:
    try:
        return WorkspaceStore().update_favorite_structure_template(
            template_id,
            request.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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


@router.post("/tasks/video-analysis/batch-start")
def start_batch_video_analysis_tasks(request: BatchAnalyzeVideosRequest) -> dict:
    try:
        return TaskService().create_batch_video_analysis_tasks(
            request.limit,
            prioritize_candidates=request.prioritize_candidates,
            video_urls=request.video_urls or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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


@router.post("/styles/merge-reports")
def merge_report_styles(request: MergeReportStylesRequest) -> dict:
    try:
        return StyleService().merge_reports(request.report_ids, name=request.name)
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
            template_id=request.template_id,
            style_id=request.style_id,
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


@router.post("/imitation-factory/projects/{project_id}/drafts")
def save_imitation_draft(project_id: str, request: SaveImitationDraftRequest) -> dict:
    try:
        return ImitationFactoryService().save_generated_draft(
            project_id=project_id,
            draft_text=request.draft_text,
            title=request.title or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/imitation-factory/projects/{project_id}/inkos/run")
def run_imitation_project_with_inkos(project_id: str, request: RunImitationInkosRequest | None = None) -> dict:
    try:
        return ImitationFactoryService().run_inkos_project(
            project_id,
            reference_run_id=request.reference_run_id if request else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InkOSRunError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": str(exc),
                "project": exc.project,
            },
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/imitation-factory/projects/{project_id}/drafts/{draft_id}/markdown")
def export_imitation_draft_markdown(project_id: str, draft_id: str) -> dict:
    try:
        return ImitationFactoryService().export_draft_markdown(project_id, draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/imitation-factory/projects/{project_id}/drafts/{draft_id}")
def update_imitation_draft(project_id: str, draft_id: str, request: UpdateImitationDraftRequest) -> dict:
    try:
        return ImitationFactoryService().update_draft_status(
            project_id=project_id,
            draft_id=draft_id,
            status=request.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/imitation-factory/projects/{project_id}/drafts/{draft_id}/reduce-risk")
def reduce_imitation_draft_risk(project_id: str, draft_id: str) -> dict:
    try:
        return ImitationFactoryService().reduce_draft_risk(project_id=project_id, draft_id=draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/imitation-factory/projects/{project_id}/drafts/{draft_id}/rewrite")
def rewrite_imitation_draft(project_id: str, draft_id: str, request: RewriteImitationDraftRequest) -> dict:
    try:
        return ImitationFactoryService().rewrite_draft(project_id=project_id, draft_id=draft_id, mode=request.mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/imitation-factory/projects/{project_id}/drafts/{draft_id}/rewrite-risk-segment")
def rewrite_imitation_draft_risk_segment(project_id: str, draft_id: str, request: RewriteRiskSegmentRequest) -> dict:
    try:
        return ImitationFactoryService().rewrite_risk_segment(
            project_id=project_id,
            draft_id=draft_id,
            segment_index=request.segment_index,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/story-workbench/reports/{report_id}")
def story_workbench(report_id: str) -> dict:
    try:
        return StoryWorkbenchService().get_for_report(report_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/story-workbench/reports/{report_id}")
def save_story_workbench(report_id: str, request: SaveStoryWorkbenchRequest) -> dict:
    try:
        return StoryWorkbenchService().save_cleaned_script(report_id, request.cleaned_text)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/story-workbench/reports/{report_id}/analysis")
def update_story_workbench_analysis(report_id: str, request: UpdateStoryAnalysisRequest) -> dict:
    try:
        return StoryWorkbenchService().update_analysis(
            report_id,
            request.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/story-workbench/reports/{report_id}/versions/{version_id}/restore")
def restore_story_workbench_version(report_id: str, version_id: str) -> dict:
    try:
        return StoryWorkbenchService().restore_cleaned_version(report_id, version_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
