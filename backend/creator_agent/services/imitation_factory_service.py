from __future__ import annotations

import re
import json
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from creator_agent.config import Settings
from creator_agent.services.settings_service import WorkspaceSettingsService
from creator_agent.services.transcript_store import TranscriptStore
from creator_agent.services.workspace_store import WorkspaceStore, unique_workspace_id


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class InkOSRunError(RuntimeError):
    def __init__(self, message: str, project: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.project = project or {}


class ImitationFactoryService:
    def __init__(self, settings: Settings | None = None, store: WorkspaceStore | None = None) -> None:
        self.settings = settings or Settings()
        self.store = store or WorkspaceStore(self.settings)

    def list_projects(self) -> dict[str, Any]:
        data = self.store.load()
        return {
            "projects": data["imitation_projects"],
            "reports": self._report_options(data),
            "ideas": self._idea_options(data),
            "templates": data["favorite_structure_templates"],
            "styles": data["style_profiles"],
            "inkos_status": self.inkos_status(),
        }

    def inkos_status(self) -> dict[str, Any]:
        command = self.settings.inkos_command.strip() or "inkos"
        parts = self._split_command(command)
        executable = parts[0] if parts else "inkos"
        resolved = self._resolve_executable(executable)
        configured = bool(resolved)
        return {
            "configured": configured,
            "command": command,
            "executable": executable,
            "resolved_path": resolved,
            "project_dir": self.settings.inkos_project_dir,
            "timeout_seconds": self.settings.inkos_timeout_seconds,
            "message": (
                "InkOS command is available."
                if configured
                else "InkOS command was not found. Install InkOS or set YCA_INKOS_COMMAND."
            ),
        }

    def create_project(
        self,
        *,
        report_id: str,
        idea_id: str | None = None,
        template_id: str | None = None,
        style_id: str | None = None,
        direction: str,
        output_type: str = "short_fiction",
        similarity_level: str = "medium",
        target_length: str = "2500-4000 Chinese characters",
        keep_narration: bool = True,
    ) -> dict[str, Any]:
        holder: dict[str, Any] = {}

        def create(data: dict[str, Any]) -> None:
            report = self._find_by_id(data["reports"], report_id)
            if not report:
                raise ValueError("Report not found.")
            idea = self._find_idea(data, idea_id or "", report_id)
            template = self._find_template(data, template_id or "")
            style = self._find_style(data, style_id or "")
            story_workbench = self._story_workbench_for_report(data, report_id)
            transcript = self._transcript_for_report(report)
            package = self._build_reference_package(
                report=report,
                idea=idea,
                transcript=transcript,
                story_workbench=story_workbench,
                direction=direction,
                output_type=output_type,
                similarity_level=similarity_level,
                target_length=target_length,
                keep_narration=keep_narration,
                cleaned_script_override=str(story_workbench.get("cleaned_text") or "") if story_workbench else "",
                template=template,
                style=style,
            )
            project = {
                "id": unique_workspace_id("imitate"),
                "name": self._project_name(report, direction),
                "source_report_id": report_id,
                "source_idea_id": idea.get("id", "") if idea else "",
                "source_template_id": template.get("id", "") if template else "",
                "source_template_name": template.get("name", "") if template else "",
                "source_style_id": style.get("id", "") if style else "",
                "source_style_name": style.get("name", "") if style else "",
                "source_video_title": report.get("video_title") or "",
                "source_video_url": report.get("video_url") or "",
                "source_channel_title": report.get("channel_title") or "",
                "source_topic_type": str(
                    (report.get("creative_breakdown") if isinstance(report.get("creative_breakdown"), dict) else {}).get("topic_type")
                    or ""
                ),
                "direction": direction.strip(),
                "output_type": output_type,
                "similarity_level": similarity_level,
                "target_length": target_length.strip(),
                "keep_narration": keep_narration,
                **package,
                "generated_drafts": [],
                "created_at": utc_now_iso(),
            }
            data["imitation_projects"].insert(0, project)
            holder["project"] = project

        self.store.update(create)
        return {"project": holder["project"]}

    def save_generated_draft(
        self,
        *,
        project_id: str,
        draft_text: str,
        title: str = "",
        source: str = "manual",
        inkos_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        draft_body = draft_text.strip()
        if not draft_body:
            raise ValueError("Draft text is required.")

        holder: dict[str, Any] = {}

        def save(data: dict[str, Any]) -> None:
            project = self._find_by_id(data["imitation_projects"], project_id)
            if not project:
                raise ValueError("Imitation project not found.")

            drafts = project.setdefault("generated_drafts", [])
            if not isinstance(drafts, list):
                drafts = []
                project["generated_drafts"] = drafts

            similarity_report = self._draft_similarity_report(project, draft_body)
            draft = {
                "id": unique_workspace_id("imitate-draft"),
                "title": title.strip() or f"Draft {len(drafts) + 1}",
                "draft_text": draft_body,
                "source": source,
                "status": self._draft_status(similarity_report),
                "similarity_report": similarity_report,
                "inkos_result": inkos_result or {},
                "created_at": utc_now_iso(),
            }
            drafts.insert(0, draft)
            project["latest_similarity_report"] = similarity_report
            self._append_similarity_history(project, draft)
            project["inkos_status"] = "draft_checked"
            holder["project"] = project
            holder["draft"] = draft

        self.store.update(save)
        return {"project": holder["project"], "draft": holder["draft"]}

    def _append_similarity_history(self, project: dict[str, Any], draft: dict[str, Any]) -> None:
        history = project.setdefault("similarity_report_history", [])
        if not isinstance(history, list):
            history = []
            project["similarity_report_history"] = history
        report = draft.get("similarity_report") if isinstance(draft.get("similarity_report"), dict) else {}
        history.insert(
            0,
            {
                "id": unique_workspace_id("similarity-report"),
                "draft_id": str(draft.get("id") or ""),
                "draft_title": str(draft.get("title") or ""),
                "draft_source": str(draft.get("source") or ""),
                "risk_level": str(report.get("risk_level") or ""),
                "text_overlap_percent": report.get("text_overlap_percent", 0),
                "structure_similarity": report.get("structure_similarity", 0),
                "style_similarity": report.get("style_similarity", 0),
                "repeated_phrase_count": len(report.get("repeated_phrases") or []),
                "reused_entity_count": len(report.get("reused_entities") or []),
                "risk_segment_count": len(report.get("risk_segments") or []),
                "created_at": str(draft.get("created_at") or utc_now_iso()),
            },
        )
        del history[20:]

    def export_draft_markdown(self, project_id: str, draft_id: str) -> dict[str, str]:
        project = self._find_by_id(self.store.load()["imitation_projects"], project_id)
        if not project:
            raise ValueError("Imitation project not found.")
        draft = self._find_by_id(project.get("generated_drafts") or [], draft_id)
        if not draft:
            raise ValueError("Draft not found.")
        title = self._slug(str(draft.get("title") or draft_id))
        return {
            "filename": f"{title}.md",
            "markdown": self._draft_release_markdown(project, draft),
        }

    def _draft_release_markdown(self, project: dict[str, Any], draft: dict[str, Any], *, heading_level: int = 1) -> str:
        heading = "#" * max(1, min(heading_level, 4))
        title = str(draft.get("title") or draft.get("id") or "Draft")
        report = draft.get("similarity_report") if isinstance(draft.get("similarity_report"), dict) else {}
        gate = report.get("quality_gate") if isinstance(report.get("quality_gate"), dict) else {}
        recommendations = [str(item) for item in report.get("recommendations") or [] if str(item).strip()]
        repeated_phrases = [str(item) for item in report.get("repeated_phrases") or [] if str(item).strip()]
        reused_entities = [str(item) for item in report.get("reused_entities") or [] if str(item).strip()]
        risk_segments = report.get("risk_segments") if isinstance(report.get("risk_segments"), list) else []
        failed_checks = [str(item) for item in gate.get("failed_checks") or [] if str(item).strip()]
        draft_text = str(draft.get("draft_text") or "").strip()

        lines = [
            f"{heading} {title}",
            "",
            f"- Project: {project.get('name') or project.get('id') or '-'}",
            f"- Source: {project.get('source_video_title') or project.get('source_video_url') or '-'}",
            f"- Direction: {project.get('direction') or '-'}",
            f"- Output: {project.get('output_type') or '-'}",
            f"- Draft status: {draft.get('status') or '-'}",
            "",
            f"{heading}# 质量与风险摘要",
            "",
            f"- Quality gate: {gate.get('status') or '-'}",
            f"- Gate summary: {gate.get('summary') or '-'}",
            f"- Next action: {gate.get('next_action') or '-'}",
            f"- Risk level: {report.get('risk_level') or '-'}",
            f"- Text overlap: {report.get('text_overlap_percent', 0)}%",
            f"- Semantic plot similarity: {round(self._safe_float(report.get('semantic_similarity')) * 100)}%",
            f"- Structure similarity: {round(self._safe_float(report.get('structure_similarity')) * 100)}%",
            f"- Style similarity: {round(self._safe_float(report.get('style_similarity')) * 100)}%",
            f"- Repeated phrases: {len(repeated_phrases)}",
            f"- Reused entities: {len(reused_entities)}",
            f"- Risk segments: {len(risk_segments)}",
        ]

        if failed_checks:
            lines.extend(["", f"{heading}# 未通过检查项", ""])
            lines.extend(f"- {item}" for item in failed_checks)

        if repeated_phrases or reused_entities:
            lines.extend(["", f"{heading}# 避抄边界", ""])
            if repeated_phrases:
                lines.append("- 需要替换的重复短语: " + ", ".join(repeated_phrases[:8]))
            if reused_entities:
                lines.append("- 需要替换的复用专名: " + ", ".join(reused_entities[:8]))

        lines.extend(["", f"{heading}# 发布前检查", ""])
        checklist = recommendations[:5] or [
            "人工确认角色名、地名、系统名和具体事件没有沿用原视频。",
            "确认开场、反转和高潮只是参考结构机制，而不是复刻桥段。",
            "确认文案已完成口播节奏和平台发布格式检查。",
        ]
        lines.extend(f"- [ ] {item}" for item in checklist)
        lines.extend(["", f"{heading}# 正文", "", draft_text, ""])
        return "\n".join(lines).strip() + "\n"

    def update_draft_status(self, *, project_id: str, draft_id: str, status: str) -> dict[str, Any]:
        if status not in {"publishable", "needs_review", "needs_revision", "discarded"}:
            raise ValueError("Unknown draft status.")

        holder: dict[str, Any] = {}

        def update(data: dict[str, Any]) -> None:
            project = self._find_by_id(data["imitation_projects"], project_id)
            if not project:
                raise ValueError("Imitation project not found.")
            draft = self._find_by_id(project.get("generated_drafts") or [], draft_id)
            if not draft:
                raise ValueError("Draft not found.")
            if status == "publishable":
                can_publish, reason = self._can_mark_publishable(draft)
                if not can_publish:
                    raise ValueError(reason)
            draft["status"] = status
            draft["updated_at"] = utc_now_iso()
            holder["project"] = project
            holder["draft"] = draft

        self.store.update(update)
        return {"project": holder["project"], "draft": holder["draft"]}

    def bulk_update_latest_draft_status(self, project_ids: list[str], status: str) -> dict[str, Any]:
        if status not in {"publishable", "needs_review", "needs_revision", "discarded"}:
            raise ValueError("Unknown draft status.")
        normalized_ids = self._normalized_project_ids(project_ids)
        if not normalized_ids:
            raise ValueError("At least one project is required.")

        holder: dict[str, Any] = {"updated": [], "skipped": []}

        def update(data: dict[str, Any]) -> None:
            projects = data["imitation_projects"]
            for project_id in normalized_ids:
                project = self._find_by_id(projects, project_id)
                if not project:
                    holder["skipped"].append({"project_id": project_id, "reason": "not_found"})
                    continue
                drafts = project.get("generated_drafts") if isinstance(project.get("generated_drafts"), list) else []
                if not drafts:
                    holder["skipped"].append({"project_id": project_id, "reason": "no_draft"})
                    continue
                latest_draft = drafts[0]
                if not isinstance(latest_draft, dict):
                    holder["skipped"].append({"project_id": project_id, "reason": "invalid_latest_draft"})
                    continue
                if status == "publishable":
                    can_publish, reason = self._can_mark_publishable(latest_draft)
                    if not can_publish:
                        holder["skipped"].append(
                            {
                                "project_id": project_id,
                                "draft_id": str(latest_draft.get("id") or ""),
                                "reason": reason,
                            }
                        )
                        continue
                latest_draft["status"] = status
                latest_draft["updated_at"] = utc_now_iso()
                holder["updated"].append(
                    {
                        "project_id": project_id,
                        "draft_id": str(latest_draft.get("id") or ""),
                        "status": status,
                    }
                )

        data, _ = self.store.update(update)
        return {
            "status": status,
            "updated_count": len(holder["updated"]),
            "skipped_count": len(holder["skipped"]),
            "updated": holder["updated"],
            "skipped": holder["skipped"],
            "projects": data["imitation_projects"],
        }

    def bulk_check_latest_drafts(self, project_ids: list[str]) -> dict[str, Any]:
        normalized_ids = self._normalized_project_ids(project_ids)
        if not normalized_ids:
            raise ValueError("At least one project is required.")

        holder: dict[str, Any] = {"checked": [], "skipped": []}

        def update(data: dict[str, Any]) -> None:
            projects = data["imitation_projects"]
            for project_id in normalized_ids:
                project = self._find_by_id(projects, project_id)
                if not project:
                    holder["skipped"].append({"project_id": project_id, "reason": "not_found"})
                    continue
                drafts = project.get("generated_drafts") if isinstance(project.get("generated_drafts"), list) else []
                if not drafts:
                    holder["skipped"].append({"project_id": project_id, "reason": "no_draft"})
                    continue
                latest_draft = drafts[0]
                if not isinstance(latest_draft, dict):
                    holder["skipped"].append({"project_id": project_id, "reason": "invalid_latest_draft"})
                    continue
                draft_text = str(latest_draft.get("draft_text") or "").strip()
                if not draft_text:
                    holder["skipped"].append({"project_id": project_id, "reason": "empty_draft"})
                    continue

                similarity_report = self._draft_similarity_report(project, draft_text)
                latest_draft["similarity_report"] = similarity_report
                latest_draft["status"] = self._draft_status(similarity_report)
                latest_draft["updated_at"] = utc_now_iso()
                project["latest_similarity_report"] = similarity_report
                project["inkos_status"] = "draft_checked"
                self._append_similarity_history(project, latest_draft)
                gate = similarity_report.get("quality_gate") if isinstance(similarity_report.get("quality_gate"), dict) else {}
                holder["checked"].append(
                    {
                        "project_id": project_id,
                        "draft_id": str(latest_draft.get("id") or ""),
                        "status": str(latest_draft.get("status") or ""),
                        "risk_level": str(similarity_report.get("risk_level") or ""),
                        "quality_gate_status": str(gate.get("status") or ""),
                        "text_overlap_percent": similarity_report.get("text_overlap_percent", 0),
                    }
                )

        data, _ = self.store.update(update)
        return {
            "checked_count": len(holder["checked"]),
            "skipped_count": len(holder["skipped"]),
            "checked": holder["checked"],
            "skipped": holder["skipped"],
            "projects": data["imitation_projects"],
        }

    def bulk_run_inkos(
        self,
        project_ids: list[str],
        *,
        skip_publishable: bool = True,
    ) -> dict[str, Any]:
        normalized_ids = self._normalized_project_ids(project_ids)
        if not normalized_ids:
            raise ValueError("At least one project is required.")
        generated: list[dict[str, str]] = []
        skipped: list[dict[str, str]] = []
        failed: list[dict[str, str]] = []

        for project_id in normalized_ids:
            project = self._find_by_id(self.store.load()["imitation_projects"], project_id)
            if not project:
                skipped.append({"project_id": project_id, "reason": "not_found"})
                continue
            if not str(project.get("reference_markdown") or "").strip():
                skipped.append({"project_id": project_id, "reason": "no_reference_package"})
                continue
            drafts = project.get("generated_drafts") if isinstance(project.get("generated_drafts"), list) else []
            latest_draft = drafts[0] if drafts and isinstance(drafts[0], dict) else {}
            if skip_publishable and str(latest_draft.get("status") or "") == "publishable":
                skipped.append({"project_id": project_id, "reason": "already_publishable"})
                continue
            try:
                result = self.run_inkos_project(project_id)
            except InkOSRunError as exc:
                failed.append({"project_id": project_id, "reason": "inkos_failed", "message": str(exc)})
                continue
            except ValueError as exc:
                skipped.append({"project_id": project_id, "reason": str(exc)})
                continue
            draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
            generated.append(
                {
                    "project_id": project_id,
                    "draft_id": str(draft.get("id") or ""),
                    "status": str(draft.get("status") or ""),
                    "title": str(draft.get("title") or ""),
                }
            )

        data = self.store.load()
        return {
            "generated_count": len(generated),
            "skipped_count": len(skipped),
            "failed_count": len(failed),
            "generated": generated,
            "skipped": skipped,
            "failed": failed,
            "projects": data["imitation_projects"],
        }

    def bulk_export_markdown(
        self,
        project_ids: list[str],
        *,
        include_reference: bool = True,
        include_latest_draft: bool = True,
    ) -> dict[str, Any]:
        normalized_ids = self._normalized_project_ids(project_ids)
        if not normalized_ids:
            raise ValueError("At least one project is required.")
        if not include_reference and not include_latest_draft:
            raise ValueError("Select reference packages, latest drafts, or both.")

        data = self.store.load()
        sections: list[str] = []
        exported: list[dict[str, str]] = []
        skipped: list[dict[str, str]] = []
        for index, project_id in enumerate(normalized_ids, start=1):
            project = self._find_by_id(data["imitation_projects"], project_id)
            if not project:
                skipped.append({"project_id": project_id, "reason": "not_found"})
                continue
            title = str(project.get("name") or project_id)
            project_sections = [f"# {index}. {title}"]
            project_sections.append("")
            project_sections.append(f"- Source: {project.get('source_video_title') or project.get('source_video_url') or '-'}")
            project_sections.append(f"- Direction: {project.get('direction') or '-'}")
            project_sections.append(f"- Output: {project.get('output_type') or '-'}")

            if include_reference:
                reference = str(project.get("reference_markdown") or "").strip()
                if reference:
                    project_sections.extend(["", "## 创作参考包", "", reference])

            if include_latest_draft:
                drafts = project.get("generated_drafts") if isinstance(project.get("generated_drafts"), list) else []
                latest_draft = drafts[0] if drafts and isinstance(drafts[0], dict) else {}
                draft_text = str(latest_draft.get("draft_text") or "").strip()
                if draft_text:
                    project_sections.extend(
                        [
                            "",
                            "## 最新草稿",
                            "",
                            self._draft_release_markdown(project, latest_draft, heading_level=3).strip(),
                        ]
                    )
                elif not include_reference:
                    skipped.append({"project_id": project_id, "reason": "no_draft"})
                    continue

            sections.append("\n".join(project_sections).strip())
            exported.append({"project_id": project_id, "name": title})

        if not sections:
            raise ValueError("No exportable project content was found.")

        return {
            "filename": "creation-projects-export.md",
            "markdown": "\n\n---\n\n".join(sections).strip() + "\n",
            "exported_count": len(exported),
            "skipped_count": len(skipped),
            "exported": exported,
            "skipped": skipped,
        }

    def reduce_draft_risk(self, *, project_id: str, draft_id: str) -> dict[str, Any]:
        project = self._find_by_id(self.store.load()["imitation_projects"], project_id)
        if not project:
            raise ValueError("Imitation project not found.")
        draft = self._find_by_id(project.get("generated_drafts") or [], draft_id)
        if not draft:
            raise ValueError("Draft not found.")

        original_text = str(draft.get("draft_text") or "")
        if not original_text.strip():
            raise ValueError("Draft text is required.")
        report = draft.get("similarity_report") if isinstance(draft.get("similarity_report"), dict) else {}
        reduced_text = self._risk_reduced_text(
            original_text,
            repeated_phrases=[str(item) for item in report.get("repeated_phrases") or []],
        )
        title = f"{draft.get('title') or 'Draft'} - 降风险版"
        result = self.save_generated_draft(
            project_id=project_id,
            draft_text=reduced_text,
            title=title,
            source="risk_rewrite",
            inkos_result={
                "parent_draft_id": draft_id,
                "rewrite_strategy": "deterministic_phrase_replacement",
            },
        )
        self._attach_rewrite_comparison(result, draft, "reduce_risk")
        result["parent_draft_id"] = draft_id
        return result

    def rewrite_draft(self, *, project_id: str, draft_id: str, mode: str) -> dict[str, Any]:
        mode = mode.strip()
        if mode not in {"faster_pacing", "stronger_opening", "short_drama", "shorts_narration", "compressed", "plot_reframe"}:
            raise ValueError("Unknown rewrite mode.")
        project = self._find_by_id(self.store.load()["imitation_projects"], project_id)
        if not project:
            raise ValueError("Imitation project not found.")
        draft = self._find_by_id(project.get("generated_drafts") or [], draft_id)
        if not draft:
            raise ValueError("Draft not found.")

        original_text = str(draft.get("draft_text") or "")
        if not original_text.strip():
            raise ValueError("Draft text is required.")
        rewritten = self._rewrite_by_mode(original_text, mode)
        result = self.save_generated_draft(
            project_id=project_id,
            draft_text=rewritten,
            title=f"{draft.get('title') or 'Draft'} - {self._rewrite_mode_label(mode)}",
            source=f"rewrite_{mode}",
            inkos_result={
                "parent_draft_id": draft_id,
                "rewrite_strategy": mode,
            },
        )
        self._attach_rewrite_comparison(result, draft, mode)
        result["parent_draft_id"] = draft_id
        return result

    def rewrite_risk_segment(self, *, project_id: str, draft_id: str, segment_index: int) -> dict[str, Any]:
        project = self._find_by_id(self.store.load()["imitation_projects"], project_id)
        if not project:
            raise ValueError("Imitation project not found.")
        draft = self._find_by_id(project.get("generated_drafts") or [], draft_id)
        if not draft:
            raise ValueError("Draft not found.")
        if segment_index < 0:
            raise ValueError("Risk segment index is required.")

        original_text = str(draft.get("draft_text") or "")
        report = draft.get("similarity_report") if isinstance(draft.get("similarity_report"), dict) else {}
        risk_segments = report.get("risk_segments") if isinstance(report.get("risk_segments"), list) else []
        if segment_index >= len(risk_segments):
            raise ValueError("Risk segment not found.")
        segment = risk_segments[segment_index] if isinstance(risk_segments[segment_index], dict) else {}
        rewritten_text, rewritten_segment = self._rewrite_text_for_risk_segment(original_text, segment)
        if rewritten_text.strip() == original_text.strip():
            raise ValueError("Unable to rewrite the selected risk segment.")

        result = self.save_generated_draft(
            project_id=project_id,
            draft_text=rewritten_text,
            title=f"{draft.get('title') or 'Draft'} - 局部降风险版",
            source="risk_segment_rewrite",
            inkos_result={
                "parent_draft_id": draft_id,
                "rewrite_strategy": "risk_segment",
                "risk_segment_index": segment_index,
                "risk_type": str(segment.get("risk_type") or ""),
                "rewritten_segment": rewritten_segment,
            },
        )
        self._attach_rewrite_comparison(result, draft, "risk_segment")
        result["parent_draft_id"] = draft_id
        result["rewritten_segment"] = rewritten_segment
        return result

    def run_inkos_project(self, project_id: str, *, reference_run_id: str | None = None) -> dict[str, Any]:
        project = self._find_by_id(self.store.load()["imitation_projects"], project_id)
        if not project:
            raise ValueError("Imitation project not found.")

        run_id = unique_workspace_id("inkos-run")
        run_dir = self._inkos_run_dir(project_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        reference_path = run_dir / "reference.md"
        reference_markdown = self._reference_for_inkos_run(project, reference_run_id)
        reference_path.write_text(reference_markdown, encoding="utf-8")
        command = self._inkos_execution_args(project, reference_path, run_dir)
        env = self._inkos_env()
        started_at = utc_now_iso()
        started = time.monotonic()
        request_snapshot = self._inkos_request_snapshot(
            project,
            reference_path,
            reference_markdown,
            reference_run_id=reference_run_id,
        )

        try:
            completed = subprocess.run(
                command,
                cwd=run_dir,
                env=env,
                text=True,
                capture_output=True,
                timeout=max(30, int(self.settings.inkos_timeout_seconds)),
                check=False,
            )
        except FileNotFoundError as exc:
            elapsed_ms = self._elapsed_ms(started)
            project_snapshot = self._record_inkos_failure(
                project_id,
                command,
                "InkOS command was not found. Install InkOS or set YCA_INKOS_COMMAND.",
                run_id=run_id,
                run_dir=run_dir,
                request_snapshot=request_snapshot,
                started_at=started_at,
                elapsed_ms=elapsed_ms,
            )
            raise InkOSRunError(
                "InkOS command was not found. Install InkOS or set YCA_INKOS_COMMAND.",
                project_snapshot,
            ) from exc
        except subprocess.TimeoutExpired as exc:
            elapsed_ms = self._elapsed_ms(started)
            project_snapshot = self._record_inkos_failure(
                project_id,
                command,
                "InkOS run timed out.",
                run_id=run_id,
                run_dir=run_dir,
                request_snapshot=request_snapshot,
                started_at=started_at,
                elapsed_ms=elapsed_ms,
            )
            raise InkOSRunError("InkOS run timed out.", project_snapshot) from exc

        if completed.returncode != 0:
            message = self._trim_process_output(completed.stderr or completed.stdout or "InkOS run failed.")
            elapsed_ms = self._elapsed_ms(started)
            project_snapshot = self._record_inkos_failure(
                project_id,
                command,
                message,
                run_id=run_id,
                run_dir=run_dir,
                request_snapshot=request_snapshot,
                started_at=started_at,
                elapsed_ms=elapsed_ms,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
            raise InkOSRunError(message, project_snapshot)

        inkos_payload = self._parse_inkos_json(completed.stdout)
        draft_text = self._inkos_draft_text(inkos_payload, run_dir, completed.stdout)
        if not draft_text.strip():
            elapsed_ms = self._elapsed_ms(started)
            project_snapshot = self._record_inkos_failure(
                project_id,
                command,
                "InkOS finished but no generated draft was found.",
                run_id=run_id,
                run_dir=run_dir,
                request_snapshot=request_snapshot,
                started_at=started_at,
                elapsed_ms=elapsed_ms,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
            raise InkOSRunError("InkOS finished but no generated draft was found.", project_snapshot)

        elapsed_ms = self._elapsed_ms(started)
        inkos_result = {
            "run_id": run_id,
            "command": command,
            "run_dir": str(run_dir),
            "reference_path": str(reference_path),
            "request": request_snapshot,
            "elapsed_ms": elapsed_ms,
            "stdout": self._trim_process_output(completed.stdout),
            "stderr": self._trim_process_output(completed.stderr),
            "result": inkos_payload,
        }
        self._record_inkos_success(
            project_id,
            command,
            run_dir,
            inkos_payload,
            run_id=run_id,
            request_snapshot=request_snapshot,
            started_at=started_at,
            elapsed_ms=elapsed_ms,
            draft_preview=draft_text[:240],
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        result = self.save_generated_draft(
            project_id=project_id,
            draft_text=draft_text,
            title=str(inkos_payload.get("storyId") or "InkOS generated draft"),
            source="inkos",
            inkos_result=inkos_result,
        )
        return result

    def _reference_for_inkos_run(self, project: dict[str, Any], reference_run_id: str | None) -> str:
        if not reference_run_id:
            return str(project.get("reference_markdown") or "")
        for run in project.get("inkos_run_history") or []:
            if not isinstance(run, dict) or str(run.get("id") or "") != reference_run_id:
                continue
            request = run.get("request") if isinstance(run.get("request"), dict) else {}
            reference_markdown = str(request.get("reference_markdown") or "")
            if reference_markdown.strip():
                return reference_markdown
            raise ValueError("Selected InkOS run does not contain a reusable reference package.")
        raise ValueError("InkOS run history item not found.")

    def _attach_rewrite_comparison(self, result: dict[str, Any], parent_draft: dict[str, Any], mode: str) -> None:
        draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
        comparison = self._rewrite_comparison(parent_draft, draft, mode)
        if not comparison:
            return
        inkos_result = draft.setdefault("inkos_result", {})
        if not isinstance(inkos_result, dict):
            inkos_result = {}
            draft["inkos_result"] = inkos_result
        inkos_result["rewrite_comparison"] = comparison
        project = result.get("project") if isinstance(result.get("project"), dict) else {}
        project_draft = self._find_by_id(project.get("generated_drafts") or [], str(draft.get("id") or ""))
        if project_draft:
            project_inkos_result = project_draft.setdefault("inkos_result", {})
            if isinstance(project_inkos_result, dict):
                project_inkos_result["rewrite_comparison"] = comparison

    def _rewrite_comparison(self, parent_draft: dict[str, Any], draft: dict[str, Any], mode: str) -> dict[str, Any]:
        before = parent_draft.get("similarity_report") if isinstance(parent_draft.get("similarity_report"), dict) else {}
        after = draft.get("similarity_report") if isinstance(draft.get("similarity_report"), dict) else {}
        if not before or not after:
            return {}
        before_gate = before.get("quality_gate") if isinstance(before.get("quality_gate"), dict) else {}
        after_gate = after.get("quality_gate") if isinstance(after.get("quality_gate"), dict) else {}
        before_overlap = self._safe_float(before.get("text_overlap_percent"))
        after_overlap = self._safe_float(after.get("text_overlap_percent"))
        before_semantic = self._safe_float(before.get("semantic_similarity"))
        after_semantic = self._safe_float(after.get("semantic_similarity"))
        before_segments = len(before.get("risk_segments") or [])
        after_segments = len(after.get("risk_segments") or [])
        return {
            "mode": mode,
            "parent_draft_id": str(parent_draft.get("id") or ""),
            "before": {
                "risk_level": str(before.get("risk_level") or ""),
                "quality_gate_status": str(before_gate.get("status") or ""),
                "text_overlap_percent": before_overlap,
                "semantic_similarity": before_semantic,
                "risk_segment_count": before_segments,
            },
            "after": {
                "risk_level": str(after.get("risk_level") or ""),
                "quality_gate_status": str(after_gate.get("status") or ""),
                "text_overlap_percent": after_overlap,
                "semantic_similarity": after_semantic,
                "risk_segment_count": after_segments,
            },
            "delta": {
                "text_overlap_percent": round(after_overlap - before_overlap, 1),
                "semantic_similarity": round(after_semantic - before_semantic, 2),
                "risk_segment_count": after_segments - before_segments,
            },
        }

    def export_markdown(self, project_id: str) -> dict[str, str]:
        project = self._find_by_id(self.store.load()["imitation_projects"], project_id)
        if not project:
            raise ValueError("Imitation project not found.")
        title = self._slug(str(project.get("name") or project_id))
        return {
            "filename": f"{title}-inkos-reference.md",
            "markdown": str(project.get("reference_markdown") or ""),
        }

    def _build_reference_package(
        self,
        *,
        report: dict[str, Any],
        idea: dict[str, Any] | None,
        transcript: dict[str, Any] | None,
        story_workbench: dict[str, Any] | None = None,
        direction: str,
        output_type: str,
        similarity_level: str,
        target_length: str,
        keep_narration: bool,
        cleaned_script_override: str = "",
        template: dict[str, Any] | None = None,
        style: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        breakdown = report.get("creative_breakdown") if isinstance(report.get("creative_breakdown"), dict) else {}
        growth = report.get("growth_judgement") if isinstance(report.get("growth_judgement"), dict) else {}
        structure = self._clean_list(breakdown.get("structure"))
        emotional_curve = self._clean_list(breakdown.get("emotional_curve"))
        story_analysis = self._story_analysis_with_evidence(story_workbench)
        story_template = self._clean_list(story_analysis.get("reusable_template")) if story_analysis else []
        story_avoid = self._clean_list(story_analysis.get("non_reusable_content")) if story_analysis else []
        growth_reasons = self._clean_list(growth.get("reasons"))
        idea_outline = self._clean_list(idea.get("outline") if idea else [])
        raw_text = str(transcript.get("raw_text") or "") if transcript else ""
        cleaned_script = cleaned_script_override.strip() or self._clean_transcript_text(raw_text)
        style_fingerprint = self._style_fingerprint(cleaned_script, breakdown, structure)
        constraints = self._constraints(similarity_level, keep_narration)
        anti_copy = self._anti_copy_rules(report, idea)
        if story_template:
            structure = story_template
        if story_avoid:
            anti_copy = self._dedupe_texts([*story_avoid, *anti_copy])
        if template:
            template_structure = self._clean_list(template.get("structure_template"))
            template_constraints = self._clean_list(template.get("reuse_constraints"))
            template_anti_copy = self._clean_list(template.get("anti_copy_rules"))
            if template_structure:
                structure = template_structure
            constraints = self._dedupe_texts([*template_constraints, *constraints])
            anti_copy = self._dedupe_texts([*template_anti_copy, *anti_copy])
        if style:
            style_constraints = self._style_constraints(style)
            style_anti_copy = self._clean_list(style.get("avoid_copying"))
            constraints = self._dedupe_texts([*style_constraints, *constraints])
            anti_copy = self._dedupe_texts([*style_anti_copy, *anti_copy])

        reference_markdown = self._reference_markdown(
            report=report,
            idea=idea,
            cleaned_script=cleaned_script,
            style_fingerprint=style_fingerprint,
            constraints=constraints,
            anti_copy=anti_copy,
            structure=structure,
            emotional_curve=emotional_curve,
            growth_reasons=growth_reasons,
            idea_outline=idea_outline,
            story_analysis=story_analysis,
            direction=direction,
            output_type=output_type,
            similarity_level=similarity_level,
            target_length=target_length,
            template=template,
            style=style,
        )
        inkos_args = self._inkos_args(direction, output_type)
        inkos_command = self._inkos_command(inkos_args)
        inkos_preview = self._inkos_generation_preview(
            reference_markdown=reference_markdown,
            target_length=target_length,
            similarity_level=similarity_level,
            keep_narration=keep_narration,
            story_analysis=story_analysis,
        )
        return {
            "reference_markdown": reference_markdown,
            "inkos_preview": inkos_preview,
            "inkos_command": inkos_command,
            "inkos_args": inkos_args,
            "structure_template": structure or idea_outline,
            "emotional_curve": emotional_curve,
            "style_fingerprint": style_fingerprint,
            "reuse_constraints": constraints,
            "anti_copy_rules": anti_copy,
            "source_script_excerpt": cleaned_script[:2200],
            "story_workbench_source": "saved_story_workbench" if story_workbench else "",
            "story_workbench_analysis": self._project_story_analysis(story_analysis),
            "source_style_profile": self._project_style_profile(style),
            "quality_checks": self._quality_checks(similarity_level),
            "risk_level": self._risk_level(similarity_level),
            "inkos_status": "reference_ready",
        }

    def _reference_markdown(
        self,
        *,
        report: dict[str, Any],
        idea: dict[str, Any] | None,
        cleaned_script: str,
        style_fingerprint: dict[str, Any],
        constraints: list[str],
        anti_copy: list[str],
        structure: list[str],
        emotional_curve: list[str],
        growth_reasons: list[str],
        idea_outline: list[str],
        story_analysis: dict[str, Any],
        direction: str,
        output_type: str,
        similarity_level: str,
        target_length: str,
        template: dict[str, Any] | None = None,
        style: dict[str, Any] | None = None,
    ) -> str:
        lines = [
            f"# InkOS 创作转化参考包：{report.get('video_title') or 'Source video'}",
            "",
            "## 生成目标",
            f"- 输出类型：{self._output_label(output_type)}",
            f"- 新故事方向：{direction.strip()}",
            f"- 目标长度：{target_length.strip()}",
            f"- 参考强度：{self._similarity_label(similarity_level)}",
            *(self._template_markdown_lines(template) if template else []),
            "",
            "## 原视频可复用机制",
            f"- 视频标题：{report.get('video_title') or ''}",
            f"- 视频链接：{report.get('video_url') or ''}",
            f"- 核心摘要：{report.get('summary') or ''}",
            f"- 标题钩子：{self._text(report, 'creative_breakdown', 'title_hook')}",
            f"- 开场钩子：{self._text(report, 'creative_breakdown', 'opening_hook')}",
            "",
            "## 结构模板",
            *self._bullets(structure or idea_outline or ["先抛出后果，再解释原因；每段推进一个信息差或反转。"]),
            "",
            *(self._story_analysis_markdown_lines(story_analysis) if story_analysis else []),
            "## 情绪曲线",
            *self._bullets(emotional_curve or ["压迫感开场", "误解加深", "第一次兑现", "身份反转", "更大悬念"]),
            "",
            "## 为什么有效",
            *self._bullets(growth_reasons or [str(idea.get("why_it_works") or "") if idea else ""]),
            "",
            "## 叙述与文风指纹",
            f"- 平均句长：{style_fingerprint['average_sentence_length']} 字",
            f"- 段落密度：{style_fingerprint['paragraph_count']} 段",
            f"- 叙述人称：{style_fingerprint['narration_person']}",
            f"- 节奏规则：{style_fingerprint['pacing_rule']}",
            f"- 转场模式：{style_fingerprint['transition_style']}",
            "",
            *(self._style_profile_markdown_lines(style) if style else []),
            "## 必须保留",
            *self._bullets(constraints),
            "",
            "## 不可复用内容与避抄边界",
            *self._bullets(anti_copy),
            "",
            "## 选题卡参考",
            f"- 标题：{idea.get('title') if idea else ''}",
            f"- 角度：{idea.get('angle') if idea else ''}",
            f"- 风险提示：{idea.get('risk_notes') if idea else '不要复用原角色名、具体事件、原句和连续桥段。'}",
            "",
            "## 原始文案摘录，仅用于风格观察",
            cleaned_script[:3200] or "暂无字幕缓存。请先完成视频分析或字幕采集。",
            "",
            "## InkOS 写作指令",
            "请根据以上参考包生成一篇新的原创短片小说/故事文案。保留结构、节奏、叙述口吻和爽点机制，但替换人物、场景、事件、设定名和具体表达。不要逐句改写原文。",
        ]
        return "\n".join(line for line in lines if line is not None)

    def _inkos_generation_preview(
        self,
        *,
        reference_markdown: str,
        target_length: str,
        similarity_level: str,
        keep_narration: bool,
        story_analysis: dict[str, Any],
    ) -> dict[str, Any]:
        reference_length = len(reference_markdown)
        estimated_input_tokens = max(1, round(reference_length / 1.6))
        estimated_output_tokens = self._target_length_tokens(target_length)
        risk_notes: list[str] = []
        checklist: list[str] = []

        if similarity_level == "high":
            risk_notes.append("参考强度较高，生成后必须重点检查叙事节奏、转场方式和连续桥段是否过度贴近。")
        elif similarity_level == "medium":
            risk_notes.append("会保留结构和节奏，建议生成后检查关键事件顺序与爽点位置。")
        else:
            risk_notes.append("主要保留故事机制，文本复用风险相对较低。")
        if reference_length > 6000:
            risk_notes.append("参考包较长，建议先确认不可复用内容和避抄边界是否清楚。")
        if keep_narration:
            risk_notes.append("保留叙述口吻会提高风格接近度，生成后需要人工确认表达没有贴近原句。")
        if story_analysis.get("manual_override"):
            checklist.append("已使用人工编辑后的故事结构。")
        else:
            checklist.append("当前使用自动结构拆解，可先在故事工坊人工校正关键节点。")
        checklist.extend(
            [
                "生成后先运行风险检测，再决定是否进入改写。",
                "高风险段落优先使用局部改写，不直接标记可发布。",
            ]
        )
        return {
            "reference_length": reference_length,
            "estimated_input_tokens": estimated_input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "estimated_total_tokens": estimated_input_tokens + estimated_output_tokens,
            "target_length": target_length.strip(),
            "similarity_level": similarity_level,
            "keep_narration": keep_narration,
            "risk_notes": risk_notes,
            "checklist": checklist,
        }

    def _target_length_tokens(self, target_length: str) -> int:
        numbers = [int(match) for match in re.findall(r"\d+", target_length or "")]
        if not numbers:
            return 2200
        average_chars = sum(numbers[:2]) / min(len(numbers), 2)
        return max(200, round(average_chars / 1.4))

    def _template_markdown_lines(self, template: dict[str, Any]) -> list[str]:
        return [
            f"- 复用收藏模板：{template.get('name') or template.get('id') or ''}",
            f"- 模板来源：{template.get('source_video_title') or template.get('source_channel_title') or ''}",
        ]

    def _style_profile_markdown_lines(self, style: dict[str, Any]) -> list[str]:
        lines = [
            "## 风格包约束",
            f"- 风格包：{style.get('name') or style.get('id') or ''}",
            f"- 来源：{style.get('source_video_title') or 'multi-source'}",
        ]
        opening = str(style.get("opening_formula") or "").strip()
        title = str(style.get("title_formula") or "").strip()
        sentence_style = str(style.get("sentence_style") or "").strip()
        if opening:
            lines.append(f"- 开场公式：{opening}")
        if title:
            lines.append(f"- 标题公式：{title}")
        if sentence_style:
            lines.append(f"- 句式风格：{sentence_style}")
        rhythm = self._clean_list(style.get("rhythm_formula"))
        emotional = self._clean_list(style.get("emotional_engine"))
        if rhythm:
            lines.extend(["", "### 节奏公式", *self._bullets(rhythm)])
        if emotional:
            lines.extend(["", "### 情绪引擎", *self._bullets(emotional)])
        reusable = self._clean_list(style.get("reusable_rules"))
        if reusable:
            lines.extend(["", "### 可复用表达规则", *self._bullets(reusable)])
        avoid = self._clean_list(style.get("avoid_copying"))
        if avoid:
            lines.extend(["", "### 风格包禁用表达", *self._bullets(avoid)])
        lines.append("")
        return lines

    def _style_constraints(self, style: dict[str, Any]) -> list[str]:
        constraints = self._clean_list(style.get("reusable_rules"))
        opening = str(style.get("opening_formula") or "").strip()
        sentence_style = str(style.get("sentence_style") or "").strip()
        rhythm = self._clean_list(style.get("rhythm_formula"))
        if opening:
            constraints.append(f"风格包开场公式：{opening}")
        if sentence_style:
            constraints.append(f"风格包句式风格：{sentence_style}")
        if rhythm:
            constraints.append("风格包节奏公式：" + " / ".join(rhythm[:6]))
        return self._dedupe_texts(constraints)

    def _project_style_profile(self, style: dict[str, Any] | None) -> dict[str, Any]:
        if not style:
            return {}
        return {
            "id": str(style.get("id") or ""),
            "name": str(style.get("name") or ""),
            "source_video_title": str(style.get("source_video_title") or ""),
            "topic_type": str(style.get("topic_type") or ""),
            "opening_formula": str(style.get("opening_formula") or ""),
            "title_formula": str(style.get("title_formula") or ""),
            "sentence_style": str(style.get("sentence_style") or ""),
            "rhythm_formula": self._clean_list(style.get("rhythm_formula")),
            "emotional_engine": self._clean_list(style.get("emotional_engine")),
            "reusable_rules": self._clean_list(style.get("reusable_rules")),
            "avoid_copying": self._clean_list(style.get("avoid_copying")),
        }

    def _story_analysis_markdown_lines(self, analysis: dict[str, Any]) -> list[str]:
        fields = [
            ("开场 5 秒钩子", analysis.get("opening_5s_hook")),
            ("前 30 秒留存机制", analysis.get("first_30s_retention")),
            ("主角初始处境", analysis.get("protagonist_position")),
            ("身份/信息/能力差", analysis.get("status_gap")),
            ("第一次爽点", analysis.get("first_payoff")),
            ("中段升级方式", analysis.get("middle_escalation")),
            ("反派/阻力设计", analysis.get("opposition_design")),
            ("公开兑现/打脸方式", analysis.get("public_reversal")),
            ("结尾悬念", analysis.get("ending_suspense")),
        ]
        evidence = analysis.get("evidence") if isinstance(analysis.get("evidence"), dict) else {}
        lines = ["## 故事工坊拆解", "以下字段来自清洗文案后的短片小说结构分析，应优先作为 InkOS 生成依据。"]
        field_keys = [
            "opening_5s_hook",
            "first_30s_retention",
            "protagonist_position",
            "status_gap",
            "first_payoff",
            "middle_escalation",
            "opposition_design",
            "public_reversal",
            "ending_suspense",
        ]
        for (label, value), field_key in zip(fields, field_keys, strict=False):
            if not str(value or "").strip():
                continue
            lines.append(f"- {label}：{str(value).strip()}")
            item = evidence.get(field_key) if isinstance(evidence.get(field_key), dict) else {}
            excerpts = [str(excerpt).strip() for excerpt in item.get("excerpts", []) if str(excerpt).strip()] if isinstance(item, dict) else []
            if excerpts:
                lines.append(f"  - 原文证据：{excerpts[0]}")
        evidence_lines = self._story_evidence_markdown_lines(fields, field_keys, evidence)
        if evidence_lines:
            lines.extend(["", "### 结构节点证据与创作边界", *evidence_lines])
        lines.append("")
        return lines

    def _story_evidence_markdown_lines(
        self,
        fields: list[tuple[str, Any]],
        field_keys: list[str],
        evidence: dict[str, Any],
    ) -> list[str]:
        lines: list[str] = []
        for (label, value), field_key in zip(fields, field_keys, strict=False):
            mechanism = str(value or "").strip()
            if not mechanism:
                continue
            item = evidence.get(field_key) if isinstance(evidence.get(field_key), dict) else {}
            excerpts = [str(excerpt).strip() for excerpt in item.get("excerpts", []) if str(excerpt).strip()] if item else []
            indexes = item.get("segment_indexes", []) if item else []
            index_label = ", ".join(str(index) for index in indexes if str(index).strip()) or "-"
            lines.append(f"- {label}")
            lines.append(f"  - 可复用机制：{mechanism}")
            if excerpts:
                lines.append(f"  - 原文证据片段（不可直接复用，段落 {index_label}）：{excerpts[0]}")
            else:
                lines.append("  - 原文证据片段：暂无，生成前建议回到故事工坊补证据。")
            lines.append("  - 创作转化边界：只保留结构功能，必须更换人物、场景、事件载体和具体表达。")
        return lines

    def _project_story_analysis(self, analysis: dict[str, Any]) -> dict[str, Any]:
        if not analysis:
            return {}
        keys = [
            "opening_5s_hook",
            "first_30s_retention",
            "protagonist_position",
            "status_gap",
            "first_payoff",
            "middle_escalation",
            "opposition_design",
            "public_reversal",
            "ending_suspense",
            "structure_confidence",
            "analysis_basis",
            "manual_override",
            "manual_updated_at",
            "evidence",
        ]
        result: dict[str, Any] = {}
        for key in keys:
            value = analysis.get(key)
            if key == "evidence":
                if isinstance(value, dict):
                    result[key] = value
            elif key == "manual_override":
                result[key] = bool(value)
            elif str(value or "").strip():
                result[key] = str(value or "")
        result["reusable_template"] = self._clean_list(analysis.get("reusable_template"))
        result["non_reusable_content"] = self._clean_list(analysis.get("non_reusable_content"))
        return result

    def _story_analysis_with_evidence(self, story_workbench: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(story_workbench, dict):
            return {}
        analysis = story_workbench.get("analysis") if isinstance(story_workbench.get("analysis"), dict) else {}
        if not analysis:
            return {}
        if isinstance(analysis.get("evidence"), dict):
            return analysis
        cleaned = str(story_workbench.get("cleaned_text") or "")
        excerpts = [item.strip() for item in cleaned.splitlines() if item.strip()]
        if not excerpts:
            return analysis
        fields = [
            "opening_5s_hook",
            "first_30s_retention",
            "protagonist_position",
            "status_gap",
            "first_payoff",
            "middle_escalation",
            "opposition_design",
            "public_reversal",
            "ending_suspense",
        ]
        evidence: dict[str, Any] = {}
        for index, field in enumerate(fields):
            excerpt = excerpts[min(index, len(excerpts) - 1)]
            evidence[field] = {
                "segment_indexes": [min(index + 1, len(excerpts))],
                "excerpts": [excerpt[:180]],
            }
        return {**analysis, "evidence": evidence}

    def _style_fingerprint(
        self,
        cleaned_script: str,
        breakdown: dict[str, Any],
        structure: list[str],
    ) -> dict[str, Any]:
        sentences = [item for item in re.split(r"[。！？!?]\s*", cleaned_script) if item.strip()]
        average = int(sum(len(item) for item in sentences) / len(sentences)) if sentences else 28
        paragraphs = [item for item in cleaned_script.splitlines() if item.strip()]
        sample = cleaned_script[:1200]
        if "我" in sample and "你" in sample:
            person = "第一/第二人称混合，像对观众直接讲述"
        elif "我" in sample:
            person = "第一人称叙述"
        elif "你" in sample:
            person = "第二人称强代入"
        else:
            person = "第三人称解说"
        return {
            "average_sentence_length": average,
            "paragraph_count": len(paragraphs),
            "narration_person": person,
            "pacing_rule": "短句推进，高频反转；每 1-2 段交代一个新信息差。" if average <= 36 else "中长句解释设定，关键节点用短句制造停顿。",
            "transition_style": "先给结果，再补原因；先制造误解，再兑现爽点。",
            "opening_formula": breakdown.get("opening_hook") or "",
            "structure_density": len(structure),
        }

    def _constraints(self, similarity_level: str, keep_narration: bool) -> list[str]:
        base = [
            "保留开场先抛后果、再补背景的顺序。",
            "保留信息差、误解、兑现、反转的推进机制。",
            "保留段落节奏：每段只推进一个清晰情绪或剧情功能。",
            "保留结尾悬念，让下一个代价、敌人或奖励浮出水面。",
        ]
        if keep_narration:
            base.append("尽量保持原视频的叙述人称、口播感和句子密度。")
        if similarity_level == "high":
            base.append("结构节点位置要高度接近原视频，但所有具体情节必须换新。")
        elif similarity_level == "low":
            base.append("只保留核心爽点机制，题材、设定和情节可以明显迁移。")
        else:
            base.append("保留结构比例和情绪曲线，同时重设人物关系和故事场景。")
        return base

    def _anti_copy_rules(self, report: dict[str, Any], idea: dict[str, Any] | None) -> list[str]:
        rules = [
            "禁止复用原视频角色名、地名、组织名、系统名和独特道具名。",
            "禁止连续复用原文句子或只做同义词替换。",
            "禁止照搬原视频的具体事件顺序；相同功能的桥段必须换成新事件。",
            "保留“为什么吸引人”的机制，不保留“发生了什么”的表层内容。",
        ]
        risk = str(idea.get("risk_notes") or "") if idea else ""
        if risk:
            rules.append(risk)
        title = str(report.get("video_title") or "").strip()
        if title:
            rules.append(f"新标题不能直接复用或轻微改写“{title}”。")
        return rules

    def _quality_checks(self, similarity_level: str) -> list[dict[str, str]]:
        return [
            {"key": "structure_match", "label": "结构相似", "target": "开场、转折、兑现、结尾悬念位置接近参考。"},
            {"key": "style_match", "label": "叙述相似", "target": "句长、口播感、信息密度和转场方式接近参考。"},
            {"key": "originality", "label": "原创安全", "target": "不得出现原句、原角色名和连续同构桥段。"},
            {"key": "mechanism_retained", "label": "爽点保留", "target": "保留信息差、误解、公开兑现或身份反转机制。"},
            {"key": "similarity_level", "label": "参考强度", "target": self._similarity_label(similarity_level)},
        ]

    def _draft_similarity_report(self, project: dict[str, Any], draft_text: str) -> dict[str, Any]:
        source_text = str(project.get("source_script_excerpt") or "")
        if not source_text.strip():
            return {
                "text_overlap_percent": 0,
                "repeated_phrases": [],
                "reused_entities": [],
                "structure_similarity": 0,
                "style_similarity": 0,
                "plot_similarity": 0,
                "pacing_similarity": 0,
                "semantic_similarity": 0,
                "risk_level": "low",
                "risk_segments": [],
                "quality_gate": self._quality_gate(
                    project=project,
                    risk_level="low",
                    overlap_percent=0,
                    repeated_phrases=[],
                    reused_entities=[],
                    structure_similarity=0,
                    style_similarity=0,
                ),
                "recommendations": ["当前项目缺少原始文案摘录，只能做基础检查；建议先在故事工坊保存清洗后的文案。"],
            }

        source_normalized = self._normalize_for_similarity(source_text)
        draft_normalized = self._normalize_for_similarity(draft_text)
        overlap_percent = self._overlap_percent(source_normalized, draft_normalized)
        repeated_phrases = self._repeated_phrases(source_text, draft_text)
        reused_entities = self._reused_entities(source_text, draft_text)
        structure_similarity = self._structure_similarity(source_text, draft_text)
        style_similarity = self._style_similarity(project, draft_text)
        plot_similarity = self._plot_similarity(source_text, draft_text)
        pacing_similarity = self._pacing_similarity(source_text, draft_text)
        semantic_similarity = self._semantic_similarity(source_text, draft_text)
        risk_level = self._draft_risk_level(
            overlap_percent,
            repeated_phrases,
            reused_entities,
            structure_similarity,
            style_similarity,
            plot_similarity,
            pacing_similarity,
            semantic_similarity,
        )
        risk_segments = self._risk_segments(
            source_text=source_text,
            draft_text=draft_text,
            repeated_phrases=repeated_phrases,
            reused_entities=reused_entities,
            structure_similarity=structure_similarity,
            style_similarity=style_similarity,
            plot_similarity=plot_similarity,
            pacing_similarity=pacing_similarity,
            semantic_similarity=semantic_similarity,
        )
        quality_gate = self._quality_gate(
            project=project,
            risk_level=risk_level,
            overlap_percent=overlap_percent,
            repeated_phrases=repeated_phrases,
            reused_entities=reused_entities,
            structure_similarity=structure_similarity,
            style_similarity=style_similarity,
            semantic_similarity=semantic_similarity,
        )
        return {
            "text_overlap_percent": overlap_percent,
            "repeated_phrases": repeated_phrases,
            "reused_entities": reused_entities,
            "structure_similarity": structure_similarity,
            "style_similarity": style_similarity,
            "plot_similarity": plot_similarity,
            "pacing_similarity": pacing_similarity,
            "semantic_similarity": semantic_similarity,
            "risk_level": risk_level,
            "risk_segments": risk_segments,
            "quality_gate": quality_gate,
            "recommendations": self._draft_recommendations(
                risk_level=risk_level,
                overlap_percent=overlap_percent,
                repeated_phrases=repeated_phrases,
                reused_entities=reused_entities,
                structure_similarity=structure_similarity,
                style_similarity=style_similarity,
                plot_similarity=plot_similarity,
                pacing_similarity=pacing_similarity,
                semantic_similarity=semantic_similarity,
            ),
        }

    def _normalize_for_similarity(self, text: str) -> str:
        return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text.lower())

    def _overlap_percent(self, source: str, draft: str) -> float:
        if len(source) < 8 or len(draft) < 8:
            return 0
        size = 8 if min(len(source), len(draft)) < 160 else 12
        source_grams = self._character_ngrams(source, size)
        draft_grams = self._character_ngrams(draft, size)
        if not source_grams or not draft_grams:
            return 0
        overlap = len(source_grams & draft_grams) / len(draft_grams)
        return round(overlap * 100, 1)

    def _character_ngrams(self, text: str, size: int) -> set[str]:
        if len(text) < size:
            return set()
        return {text[index : index + size] for index in range(0, len(text) - size + 1)}

    def _repeated_phrases(self, source_text: str, draft_text: str) -> list[str]:
        draft_normalized = self._normalize_for_similarity(draft_text)
        repeated: list[str] = []
        seen: set[str] = set()
        candidates = re.split(r"[\n。！？!?；;,.，、]+", source_text)
        for candidate in candidates:
            phrase = candidate.strip()
            normalized = self._normalize_for_similarity(phrase)
            if len(normalized) < 10 or normalized in seen:
                continue
            if normalized in draft_normalized:
                repeated.append(phrase[:80])
                seen.add(normalized)
            if len(repeated) >= 8:
                return repeated

        source_normalized = self._normalize_for_similarity(source_text)
        for size in (18, 14, 10):
            for gram in self._character_ngrams(source_normalized, size):
                if gram in draft_normalized and gram not in seen:
                    repeated.append(gram)
                    seen.add(gram)
                if len(repeated) >= 8:
                    return repeated
        return repeated

    def _reused_entities(self, source_text: str, draft_text: str) -> list[str]:
        draft_normalized = self._normalize_for_similarity(draft_text)
        entities: list[str] = []
        seen: set[str] = set()
        for entity in self._entity_candidates(source_text):
            normalized = self._normalize_for_similarity(entity)
            if len(normalized) < 2 or normalized in seen:
                continue
            if normalized in draft_normalized:
                entities.append(entity[:40])
                seen.add(normalized)
            if len(entities) >= 10:
                break
        return entities

    def _entity_candidates(self, text: str) -> list[str]:
        candidates: list[str] = []
        suffix_pattern = r"(系统|协议|令|剑|刀|戒|塔|城|村|镇|国|宗|门|阁|殿|宫|学院|公司|集团|组织|计划|实验室|芯片|引擎)"
        for match in re.finditer(suffix_pattern, text):
            suffix = match.group(1)
            prefix = self._entity_prefix(text[: match.start()])
            max_prefix_length = min(4, len(prefix))
            for prefix_length in range(max_prefix_length, 0, -1):
                candidates.append(f"{prefix[-prefix_length:]}{suffix}")
        candidates.extend(re.findall(r"(?:[A-Z][a-zA-Z0-9_-]{2,}|[A-Z]{2,})(?:\s+[A-Z][a-zA-Z0-9_-]{2,})?", text))
        candidates.extend(re.findall(r"(?:叫|名叫|主角是|反派是|女孩叫|男孩叫)([\u4e00-\u9fff]{2,4})", text))
        return [candidate.strip() for candidate in candidates if self._is_entity_candidate(candidate.strip())]

    def _entity_prefix(self, text: str) -> str:
        match = re.search(r"[\u4e00-\u9fffA-Za-z0-9_-]{1,12}$", text)
        return match.group(0) if match else ""

    def _is_entity_candidate(self, value: str) -> bool:
        if not value:
            return False
        normalized = self._normalize_for_similarity(value)
        if len(normalized) < 2:
            return False
        english_stopwords = {
            "a",
            "an",
            "and",
            "but",
            "he",
            "her",
            "his",
            "it",
            "she",
            "the",
            "their",
            "they",
            "this",
        }
        if normalized in english_stopwords:
            return False
        common_terms = {
            "隐藏系统",
            "所有人",
            "实习生",
            "全场",
            "视频",
            "故事",
            "主角",
            "反派",
        }
        if value in common_terms:
            return False
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", value):
            return True
        if re.search(r"(系统|协议|令|剑|刀|戒|塔|城|村|镇|国|宗|门|阁|殿|宫|学院|公司|集团|组织|计划|实验室|芯片|引擎)$", value):
            return True
        return bool(re.search(r"[A-Z]", value))

    def _risk_segments(
        self,
        *,
        source_text: str,
        draft_text: str,
        repeated_phrases: list[str],
        reused_entities: list[str],
        structure_similarity: float,
        style_similarity: float,
        plot_similarity: float,
        pacing_similarity: float,
        semantic_similarity: float,
    ) -> list[dict[str, Any]]:
        draft_sentences = self._sentences_with_index(draft_text)
        source_sentences = self._sentences_with_index(source_text)
        segments: list[dict[str, Any]] = []
        seen: set[str] = set()

        for phrase in repeated_phrases:
            normalized_phrase = self._normalize_for_similarity(phrase)
            if len(normalized_phrase) < 4:
                continue
            draft_match = self._sentence_containing(draft_sentences, normalized_phrase)
            source_match = self._sentence_containing(source_sentences, normalized_phrase)
            key = self._normalize_for_similarity(str(draft_match.get("text") or phrase))[:80]
            if not key or key in seen:
                continue
            seen.add(key)
            segments.append(
                {
                    "risk_type": "text_overlap",
                    "severity": "high" if len(normalized_phrase) >= 10 else "medium",
                    **self._risk_action("high" if len(normalized_phrase) >= 10 else "medium"),
                    **self._risk_segment_diagnosis("text_overlap"),
                    "draft_excerpt": str(draft_match.get("text") or phrase)[:180],
                    "source_excerpt": str(source_match.get("text") or phrase)[:180],
                    "matched_text": phrase[:120],
                    "draft_index": draft_match.get("index", 0),
                    "recommendation": "重写这句的动作、名词和句式，不要只替换同义词。",
                }
            )
            if len(segments) >= 6:
                return segments

        for entity in reused_entities:
            normalized_entity = self._normalize_for_similarity(entity)
            draft_match = self._sentence_containing(draft_sentences, normalized_entity)
            source_match = self._sentence_containing(source_sentences, normalized_entity)
            key = f"entity-{normalized_entity}"
            if not normalized_entity or key in seen:
                continue
            seen.add(key)
            segments.append(
                {
                    "risk_type": "entity_reuse",
                    "severity": "high",
                    **self._risk_action("high"),
                    **self._risk_segment_diagnosis("entity_reuse"),
                    "draft_excerpt": str(draft_match.get("text") or entity)[:180],
                    "source_excerpt": str(source_match.get("text") or entity)[:180],
                    "matched_text": entity[:120],
                    "draft_index": draft_match.get("index", 0),
                    "recommendation": "替换这个角色名、地名、系统名或道具名，并同步改掉相关设定。拷贝专有名会显著提高照抄风险。",
                }
            )
            if len(segments) >= 6:
                return segments

        if semantic_similarity >= 0.78:
            for index, sentence in enumerate(draft_sentences[:4]):
                source_sentence = source_sentences[index] if index < len(source_sentences) else {}
                key = f"semantic-{index}-{self._plot_label(str(sentence.get('text') or ''))}"
                if key in seen:
                    continue
                seen.add(key)
                segments.append(
                    {
                        "risk_type": "semantic_plot",
                        "severity": "medium",
                        **self._risk_action("medium"),
                        **self._risk_segment_diagnosis("semantic_plot"),
                        "draft_excerpt": str(sentence.get("text") or "")[:180],
                        "source_excerpt": str(source_sentence.get("text") or "")[:180],
                        "matched_text": "",
                        "draft_index": sentence.get("index", index),
                        "recommendation": "这段虽然换了表达，但情节功能和关键动作仍接近；建议更换事件载体、动机或兑现方式。",
                    }
                )
                if len(segments) >= 6:
                    return segments

        if plot_similarity >= 0.86:
            for index, sentence in enumerate(draft_sentences[:4]):
                key = self._normalize_for_similarity(str(sentence.get("text") or ""))[:80]
                if not key or key in seen:
                    continue
                seen.add(key)
                segments.append(
                    {
                        "risk_type": "plot_order",
                        "severity": "medium",
                        **self._risk_action("medium"),
                        **self._risk_segment_diagnosis("plot_order"),
                        "draft_excerpt": str(sentence.get("text") or "")[:180],
                        "source_excerpt": str(source_sentences[index].get("text") or "")[:180] if index < len(source_sentences) else "",
                        "matched_text": "",
                        "draft_index": sentence.get("index", index),
                        "recommendation": "关键桥段顺序过近，建议调换至少一个转折、兑现或阻力节点，并替换对应事件。",
                    }
                )
                if len(segments) >= 6:
                    return segments

        if pacing_similarity >= 0.9:
            for index, sentence in enumerate(draft_sentences[:3]):
                key = f"pacing-{index}-{len(str(sentence.get('text') or ''))}"
                if key in seen:
                    continue
                seen.add(key)
                segments.append(
                    {
                        "risk_type": "pacing",
                        "severity": "medium",
                        **self._risk_action("medium"),
                        **self._risk_segment_diagnosis("pacing"),
                        "draft_excerpt": str(sentence.get("text") or "")[:180],
                        "source_excerpt": str(source_sentences[index].get("text") or "")[:180] if index < len(source_sentences) else "",
                        "matched_text": "",
                        "draft_index": sentence.get("index", index),
                        "recommendation": "句段节奏过近，建议拆分或合并句子，改变信息释放速度。",
                    }
                )
                if len(segments) >= 6:
                    return segments

        if structure_similarity >= 0.86 and style_similarity >= 0.86:
            for index, sentence in enumerate(draft_sentences[:3]):
                key = self._normalize_for_similarity(str(sentence.get("text") or ""))[:80]
                if not key or key in seen:
                    continue
                seen.add(key)
                segments.append(
                    {
                        "risk_type": "structure_style",
                        "severity": "medium",
                        **self._risk_action("medium"),
                        **self._risk_segment_diagnosis("structure_style"),
                        "draft_excerpt": str(sentence.get("text") or "")[:180],
                        "source_excerpt": str(source_sentences[index].get("text") or "")[:180] if index < len(source_sentences) else "",
                        "matched_text": "",
                        "draft_index": sentence.get("index", index),
                        "recommendation": "这段的结构和句式节奏过近，建议调整转折顺序或拆分/合并句子。",
                    }
                )
                if len(segments) >= 6:
                    break
        return segments

    def _risk_segment_diagnosis(self, risk_type: str) -> dict[str, Any]:
        diagnoses: dict[str, dict[str, Any]] = {
            "text_overlap": {
                "similarity_reason": "连续表达、动作或关键短语与来源文本重合。",
                "suggested_rewrite_mode": "reduce_risk",
                "rewrite_goal": "重写句式、动作和名词，避免保留连续原句或半句。",
                "must_replace": ["连续原句", "关键动作", "同序名词"],
                "can_keep": ["冲突功能", "情绪压力"],
            },
            "entity_reuse": {
                "similarity_reason": "角色名、地点名、系统名或道具名与来源文本复用。",
                "suggested_rewrite_mode": "reduce_risk",
                "rewrite_goal": "替换专名，并同步改写围绕该专名展开的设定。",
                "must_replace": ["专名", "道具名", "相关设定"],
                "can_keep": ["角色功能", "关系压力"],
            },
            "semantic_plot": {
                "similarity_reason": "虽然换了表达，但事件功能、触发方式或兑现方式仍接近来源桥段。",
                "suggested_rewrite_mode": "plot_reframe",
                "rewrite_goal": "更换事件载体、人物动机、证据来源和公开反转场景。",
                "must_replace": ["事件载体", "触发动机", "兑现方式", "公开反转场景"],
                "can_keep": ["压力-触发-兑现-反转的结构功能"],
            },
            "plot_order": {
                "similarity_reason": "关键事件顺序与来源文本过近，容易形成照搬桥段推进。",
                "suggested_rewrite_mode": "plot_reframe",
                "rewrite_goal": "调换至少一个压力、触发、阻力或兑现节点，并改变对应事件。",
                "must_replace": ["事件顺序", "转折节点", "阻力来源"],
                "can_keep": ["爽点节奏", "公开反转功能"],
            },
            "pacing": {
                "similarity_reason": "句长、停顿和信息释放位置与来源文本接近。",
                "suggested_rewrite_mode": "faster_pacing",
                "rewrite_goal": "拆分或合并句子，改变信息释放速度和段落停顿。",
                "must_replace": ["句长结构", "停顿位置", "信息释放顺序"],
                "can_keep": ["紧张感", "情绪递进"],
            },
            "structure_style": {
                "similarity_reason": "结构功能和句式节奏同时接近，容易显得只是摘要式改写。",
                "suggested_rewrite_mode": "stronger_opening",
                "rewrite_goal": "重排转折顺序，并重写开场、段落节奏和叙述视角。",
                "must_replace": ["开场表达", "段落节奏", "叙述视角"],
                "can_keep": ["结构机制", "目标情绪"],
            },
        }
        return diagnoses.get(
            risk_type,
            {
                "similarity_reason": "该段落与来源文本存在相似风险。",
                "suggested_rewrite_mode": "reduce_risk",
                "rewrite_goal": "替换具体表达和事件细节，保留抽象结构功能。",
                "must_replace": ["具体表达", "事件细节"],
                "can_keep": ["抽象结构功能"],
            },
        )

    def _risk_action(self, severity: str) -> dict[str, str]:
        if severity == "high":
            return {"action_level": "must_fix", "action_label": "必须修改"}
        if severity == "medium":
            return {"action_level": "should_fix", "action_label": "建议修改"}
        return {"action_level": "acceptable", "action_label": "可接受"}

    def _sentences_with_index(self, text: str) -> list[dict[str, Any]]:
        parts = [item.strip() for item in re.split(r"[。！？!?\n]+", text) if item.strip()]
        return [{"index": index + 1, "text": part} for index, part in enumerate(parts)]

    def _sentence_containing(self, sentences: list[dict[str, Any]], normalized_phrase: str) -> dict[str, Any]:
        for sentence in sentences:
            if normalized_phrase in self._normalize_for_similarity(str(sentence.get("text") or "")):
                return sentence
        return sentences[0] if sentences else {"index": 0, "text": ""}

    def _structure_similarity(self, source_text: str, draft_text: str) -> float:
        source_metrics = self._text_metrics(source_text)
        draft_metrics = self._text_metrics(draft_text)
        paragraph_score = self._ratio_score(source_metrics["paragraph_count"], draft_metrics["paragraph_count"])
        sentence_score = self._ratio_score(source_metrics["sentence_count"], draft_metrics["sentence_count"])
        length_score = self._ratio_score(source_metrics["average_sentence_length"], draft_metrics["average_sentence_length"])
        return round((paragraph_score * 0.35) + (sentence_score * 0.35) + (length_score * 0.3), 2)

    def _style_similarity(self, project: dict[str, Any], draft_text: str) -> float:
        style = project.get("style_fingerprint") if isinstance(project.get("style_fingerprint"), dict) else {}
        target_average = int(style.get("average_sentence_length") or 0)
        if not target_average:
            return self._structure_similarity(str(project.get("source_script_excerpt") or ""), draft_text)
        draft_average = self._text_metrics(draft_text)["average_sentence_length"]
        return round(self._ratio_score(target_average, draft_average), 2)

    def _plot_similarity(self, source_text: str, draft_text: str) -> float:
        source_labels = self._plot_sequence(source_text)
        draft_labels = self._plot_sequence(draft_text)
        if not source_labels or not draft_labels:
            return 0
        length = min(len(source_labels), len(draft_labels), 8)
        if length <= 0:
            return 0
        matches = sum(1 for index in range(length) if source_labels[index] == draft_labels[index])
        coverage = self._ratio_score(len(source_labels), len(draft_labels))
        return round(((matches / length) * 0.75) + (coverage * 0.25), 2)

    def _plot_sequence(self, text: str) -> list[str]:
        labels: list[str] = []
        for sentence in self._sentences_with_index(text)[:8]:
            labels.append(self._plot_label(str(sentence.get("text") or "")))
        return labels

    def _plot_label(self, sentence: str) -> str:
        normalized = sentence.lower()
        if any(token in normalized for token in ["瞧不起", "嘲笑", "羞辱", "质疑", "低估", "humiliation", "pressure"]):
            return "pressure"
        if any(token in normalized for token in ["隐藏", "秘密", "规则", "系统", "触发", "secret", "hidden", "trigger"]):
            return "hidden_trigger"
        if any(token in normalized for token in ["奖励", "兑现", "回报", "亮起", "reward", "payoff"]):
            return "payoff"
        if any(token in normalized for token in ["全场", "公开", "当众", "沉默", "反转", "public", "reversal"]):
            return "public_reversal"
        if any(token in normalized for token in ["敌人", "更大", "悬念", "代价", "suspense", "enemy"]):
            return "suspense"
        return "setup"

    def _pacing_similarity(self, source_text: str, draft_text: str) -> float:
        source_lengths = self._sentence_length_profile(source_text)
        draft_lengths = self._sentence_length_profile(draft_text)
        if not source_lengths or not draft_lengths:
            return 0
        length = min(len(source_lengths), len(draft_lengths), 8)
        scores = [
            self._ratio_score(source_lengths[index], draft_lengths[index])
            for index in range(length)
        ]
        coverage = self._ratio_score(len(source_lengths), len(draft_lengths))
        return round(((sum(scores) / len(scores)) * 0.8) + (coverage * 0.2), 2)

    def _sentence_length_profile(self, text: str) -> list[int]:
        return [
            max(1, len(self._normalize_for_similarity(str(sentence.get("text") or ""))))
            for sentence in self._sentences_with_index(text)[:8]
        ]

    def _semantic_similarity(self, source_text: str, draft_text: str) -> float:
        source_units = self._semantic_units(source_text)
        draft_units = self._semantic_units(draft_text)
        if not source_units or not draft_units:
            return 0
        length = min(len(source_units), len(draft_units), 8)
        scores: list[float] = []
        for index in range(length):
            source_unit = source_units[index]
            draft_unit = draft_units[index]
            label_score = 1.0 if source_unit["label"] == draft_unit["label"] else 0.0
            token_score = self._token_overlap_score(source_unit["tokens"], draft_unit["tokens"])
            scores.append((label_score * 0.55) + (token_score * 0.45))
        coverage = self._ratio_score(len(source_units), len(draft_units))
        return round(((sum(scores) / len(scores)) * 0.8) + (coverage * 0.2), 2)

    def _semantic_units(self, text: str) -> list[dict[str, Any]]:
        units: list[dict[str, Any]] = []
        for sentence in self._sentences_with_index(text)[:8]:
            sentence_text = str(sentence.get("text") or "")
            units.append(
                {
                    "label": self._plot_label(sentence_text),
                    "tokens": set(self._semantic_tokens(sentence_text)),
                }
            )
        return units

    def _semantic_tokens(self, text: str) -> list[str]:
        normalized = text.lower()
        groups = {
            "underdog": ["实习", "低估", "瞧不起", "新人", "intern", "ignored", "underestimated", "rookie"],
            "public_pressure": ["全场", "公开", "当众", "会议", "众人", "public", "meeting", "everyone", "crowd"],
            "hidden_power": ["隐藏", "系统", "规则", "秘密", "线索", "hidden", "secret", "system", "rule", "clue"],
            "evidence": ["证据", "日志", "合同", "录像", "记录", "evidence", "log", "record", "contract", "proof"],
            "opponent": ["反派", "对手", "经理", "老板", "敌人", "rival", "manager", "enemy", "opponent"],
            "payoff": ["奖励", "兑现", "反转", "沉默", "真相", "reward", "payoff", "reversal", "truth", "silent"],
        }
        tokens: list[str] = []
        for label, variants in groups.items():
            if any(variant in normalized for variant in variants):
                tokens.append(label)
        if not tokens:
            tokens.extend(re.findall(r"[a-z]{4,}|[\u4e00-\u9fff]{2,}", normalized)[:4])
        return tokens

    def _token_overlap_score(self, source_tokens: set[str], draft_tokens: set[str]) -> float:
        if not source_tokens or not draft_tokens:
            return 0
        return len(source_tokens & draft_tokens) / len(source_tokens | draft_tokens)

    def _text_metrics(self, text: str) -> dict[str, int]:
        paragraphs = [item for item in text.splitlines() if item.strip()]
        sentences = [item.strip() for item in re.split(r"[。！？!?\n]+", text) if item.strip()]
        average = int(sum(len(self._normalize_for_similarity(item)) for item in sentences) / len(sentences)) if sentences else 0
        return {
            "paragraph_count": max(len(paragraphs), 1 if text.strip() else 0),
            "sentence_count": len(sentences),
            "average_sentence_length": average,
        }

    def _ratio_score(self, source_value: int, draft_value: int) -> float:
        if source_value <= 0 or draft_value <= 0:
            return 0
        return min(source_value, draft_value) / max(source_value, draft_value)

    def _draft_risk_level(
        self,
        overlap_percent: float,
        repeated_phrases: list[str],
        reused_entities: list[str],
        structure_similarity: float,
        style_similarity: float,
        plot_similarity: float,
        pacing_similarity: float,
        semantic_similarity: float,
    ) -> str:
        if overlap_percent >= 18 or len(repeated_phrases) >= 3 or len(reused_entities) >= 2:
            return "high"
        if (
            overlap_percent >= 8
            or repeated_phrases
            or reused_entities
            or plot_similarity >= 0.9
            or pacing_similarity >= 0.94
            or semantic_similarity >= 0.82
            or (structure_similarity >= 0.86 and style_similarity >= 0.86)
        ):
            return "medium"
        return "low"

    def _draft_recommendations(
        self,
        *,
        risk_level: str,
        overlap_percent: float,
        repeated_phrases: list[str],
        reused_entities: list[str],
        structure_similarity: float,
        style_similarity: float,
        plot_similarity: float,
        pacing_similarity: float,
        semantic_similarity: float,
    ) -> list[str]:
        recommendations: list[str] = []
        if repeated_phrases:
            recommendations.append("替换检测到的重复短语，不要保留原句或连续半句。")
        if reused_entities:
            recommendations.append("替换复用的角色名、地名、系统名或道具名，并重新设计相关设定。")
        if overlap_percent >= 8:
            recommendations.append("降低逐字重合度：重写桥段表达，并替换关键名词、动作和场景。")
        if structure_similarity >= 0.86 and style_similarity >= 0.86:
            recommendations.append("结构和句式都很接近时，至少重排一个关键转折或改写段落节奏。")
        if plot_similarity >= 0.9:
            recommendations.append("桥段顺序过近：调换压力、触发、兑现或反转节点，不要照搬事件推进顺序。")
        if pacing_similarity >= 0.94:
            recommendations.append("叙事节奏过近：调整句长、分段和信息释放速度，避免同样的停顿位置。")
        if semantic_similarity >= 0.82:
            recommendations.append("语义桥段过近：不要只替换词语，改掉事件载体、动机、兑现方式或公开反转场景。")
        if risk_level == "low":
            recommendations.append("当前重复风险较低，继续确认角色名、地名、系统名和具体事件没有沿用原视频。")
        elif risk_level == "medium":
            recommendations.append("建议二次改写高相似段落后再进入发布前人工审稿。")
        else:
            recommendations.append("不建议直接使用；先做大幅改写，再重新检测。")
        return recommendations

    def _quality_gate(
        self,
        *,
        project: dict[str, Any],
        risk_level: str,
        overlap_percent: float,
        repeated_phrases: list[str],
        reused_entities: list[str],
        structure_similarity: float,
        style_similarity: float,
        semantic_similarity: float = 0,
    ) -> dict[str, Any]:
        similarity_level = str(project.get("similarity_level") or "medium")
        targets = self._quality_targets(similarity_level)
        checks = [
            {
                "key": "text_overlap",
                "label": "文本重合",
                "passed": overlap_percent <= targets["max_overlap_percent"],
                "value": overlap_percent,
                "target": f"<= {targets['max_overlap_percent']}%",
            },
            {
                "key": "repeated_phrases",
                "label": "原句/短语复用",
                "passed": len(repeated_phrases) <= targets["max_repeated_phrases"],
                "value": len(repeated_phrases),
                "target": f"<= {targets['max_repeated_phrases']}",
            },
            {
                "key": "reused_entities",
                "label": "专名复用",
                "passed": len(reused_entities) <= targets["max_reused_entities"],
                "value": len(reused_entities),
                "target": f"<= {targets['max_reused_entities']}",
            },
            {
                "key": "structure_similarity",
                "label": "结构保留",
                "passed": structure_similarity >= targets["min_structure_similarity"],
                "value": round(structure_similarity, 2),
                "target": f">= {targets['min_structure_similarity']}",
            },
            {
                "key": "style_similarity",
                "label": "文风接近",
                "passed": style_similarity >= targets["min_style_similarity"],
                "value": round(style_similarity, 2),
                "target": f">= {targets['min_style_similarity']}",
            },
            {
                "key": "semantic_similarity",
                "label": "语义桥段",
                "passed": semantic_similarity <= targets["max_semantic_similarity"],
                "value": round(semantic_similarity, 2),
                "target": f"<= {targets['max_semantic_similarity']}",
            },
        ]
        failed = [check for check in checks if not check["passed"]]
        if risk_level == "high" or any(check["key"] in {"text_overlap", "repeated_phrases", "reused_entities"} for check in failed):
            status = "blocked"
            summary = "不建议发布"
            next_action = "先降低文本、短语或专名复用风险，再重新检测。"
        elif failed:
            status = "needs_revision"
            summary = "需要修改"
            next_action = "补强结构或文风贴合度后重新检测。"
        else:
            status = "pass"
            summary = "可进入人工终审"
            next_action = "可标记为可发布，但仍需人工确认具体设定没有沿用原视频。"
        return {
            "status": status,
            "passed": status == "pass",
            "summary": summary,
            "target_similarity_level": similarity_level,
            "checks": checks,
            "failed_checks": [str(check["key"]) for check in failed],
            "next_action": next_action,
        }

    def _quality_targets(self, similarity_level: str) -> dict[str, float | int]:
        if similarity_level == "high":
            return {
                "max_overlap_percent": 7,
                "max_repeated_phrases": 0,
                "max_reused_entities": 0,
                "min_structure_similarity": 0.45,
                "min_style_similarity": 0.45,
                "max_semantic_similarity": 0.9,
            }
        if similarity_level == "low":
            return {
                "max_overlap_percent": 5,
                "max_repeated_phrases": 0,
                "max_reused_entities": 0,
                "min_structure_similarity": 0.2,
                "min_style_similarity": 0.2,
                "max_semantic_similarity": 0.78,
            }
        return {
            "max_overlap_percent": 6,
            "max_repeated_phrases": 0,
            "max_reused_entities": 0,
            "min_structure_similarity": 0.32,
            "min_style_similarity": 0.32,
            "max_semantic_similarity": 0.82,
        }

    def _risk_reduced_text(self, draft_text: str, repeated_phrases: list[str]) -> str:
        rewritten = draft_text
        for phrase in sorted(repeated_phrases, key=len, reverse=True):
            if len(self._normalize_for_similarity(phrase)) < 4:
                continue
            rewritten = rewritten.replace(phrase, self._generic_rewrite_phrase(phrase))

        paragraphs = [item.strip() for item in re.split(r"\n+", rewritten) if item.strip()]
        if len(paragraphs) > 2:
            rewritten = "\n".join([paragraphs[0], *paragraphs[2:], paragraphs[1]])

        rewritten = self._rewrite_reusable_terms(rewritten)
        if rewritten == draft_text:
            rewritten = self._soft_rewrite_sentences(rewritten)
        return rewritten.strip()

    def _rewrite_text_for_risk_segment(self, draft_text: str, segment: dict[str, Any]) -> tuple[str, str]:
        draft_excerpt = str(segment.get("draft_excerpt") or "").strip()
        matched_text = str(segment.get("matched_text") or "").strip()
        replacement_target = draft_excerpt or matched_text
        if not replacement_target:
            return draft_text, ""

        rewritten_segment = self._rewrite_risk_segment_text(
            replacement_target,
            matched_text=matched_text,
            risk_type=str(segment.get("risk_type") or ""),
        )
        if not rewritten_segment:
            return draft_text, ""
        if draft_excerpt and draft_excerpt in draft_text:
            return draft_text.replace(draft_excerpt, rewritten_segment, 1), rewritten_segment
        if matched_text and matched_text in draft_text:
            return draft_text.replace(matched_text, rewritten_segment, 1), rewritten_segment

        draft_index = self._safe_int(segment.get("draft_index"))
        if draft_index > 0:
            sentences = self._sentences_with_delimiters(draft_text)
            sentence_slot = draft_index - 1
            if 0 <= sentence_slot < len(sentences):
                sentences[sentence_slot]["text"] = rewritten_segment
                return self._join_sentences_with_delimiters(sentences), rewritten_segment
        return draft_text, ""

    def _rewrite_risk_segment_text(self, text: str, *, matched_text: str, risk_type: str) -> str:
        rewritten = text
        if matched_text and matched_text in rewritten:
            rewritten = rewritten.replace(matched_text, self._generic_rewrite_phrase(matched_text))
        rewritten = self._rewrite_reusable_terms(rewritten)
        if risk_type == "entity_reuse" and matched_text:
            rewritten = rewritten.replace(matched_text, self._generic_rewrite_phrase(matched_text))
        if self._normalize_for_similarity(rewritten) == self._normalize_for_similarity(text):
            sentences = self._plain_sentences(text)
            base = sentences[0] if sentences else text
            rewritten = f"局面换到全新的场景里，{self._trim_sentence(base)}，随后用另一组人物关系引出反转"
        return rewritten.strip()

    def _sentences_with_delimiters(self, text: str) -> list[dict[str, str]]:
        matches = list(re.finditer(r"([^。！？!?\n]+)([。！？!?]|\n+|$)", text))
        if not matches:
            return [{"text": text, "delimiter": ""}]
        return [
            {"text": match.group(1).strip(), "delimiter": match.group(2)}
            for match in matches
            if match.group(1).strip()
        ]

    def _join_sentences_with_delimiters(self, sentences: list[dict[str, str]]) -> str:
        return "".join(f"{item.get('text', '').strip()}{item.get('delimiter', '')}" for item in sentences).strip()

    def _generic_rewrite_phrase(self, phrase: str) -> str:
        normalized_length = len(self._normalize_for_similarity(phrase))
        if normalized_length >= 18:
            return "众人的判断被一个全新的意外打破"
        if normalized_length >= 10:
            return "局面突然改写"
        return "转折出现"

    def _rewrite_reusable_terms(self, text: str) -> str:
        replacements = {
            "实习生": "新人维修师",
            "系统": "核心协议",
            "奖励": "权限回响",
            "全场": "围观的人群",
            "沉默": "意识到判断错了",
            "瞧不起": "低估",
            "隐藏": "未公开",
        }
        rewritten = text
        for source, target in replacements.items():
            rewritten = rewritten.replace(source, target)
        return rewritten

    def _soft_rewrite_sentences(self, text: str) -> str:
        sentences = [item.strip() for item in re.split(r"([。！？!?])", text) if item.strip()]
        rebuilt: list[str] = []
        index = 0
        while index < len(sentences):
            sentence = sentences[index]
            punctuation = sentences[index + 1] if index + 1 < len(sentences) and re.fullmatch(r"[。！？!?]", sentences[index + 1]) else "。"
            rebuilt.append(f"换一个场景来看，{sentence}{punctuation}")
            index += 2 if index + 1 < len(sentences) and punctuation == sentences[index + 1] else 1
        return "".join(rebuilt)

    def _rewrite_by_mode(self, text: str, mode: str) -> str:
        if mode == "faster_pacing":
            return self._rewrite_faster_pacing(text)
        if mode == "stronger_opening":
            return self._rewrite_stronger_opening(text)
        if mode == "short_drama":
            return self._rewrite_short_drama(text)
        if mode == "compressed":
            return self._rewrite_compressed(text)
        if mode == "plot_reframe":
            return self._rewrite_plot_reframe(text)
        return self._rewrite_shorts_narration(text)

    def _rewrite_mode_label(self, mode: str) -> str:
        return {
            "faster_pacing": "节奏加速版",
            "stronger_opening": "强开场版",
            "short_drama": "短剧对白版",
            "shorts_narration": "Shorts 口播版",
            "compressed": "压缩篇幅版",
            "plot_reframe": "桥段重构版",
        }[mode]

    def _rewrite_faster_pacing(self, text: str) -> str:
        sentences = self._plain_sentences(text)
        tightened = [self._trim_sentence(sentence) for sentence in sentences if sentence]
        return "。\n".join(tightened[:12]) + ("。" if tightened else "")

    def _rewrite_stronger_opening(self, text: str) -> str:
        sentences = self._plain_sentences(text)
        first = sentences[0] if sentences else text.strip()
        hook = f"没人想到，真正的反转会从这一刻开始：{first}"
        rest = sentences[1:]
        return "。\n".join([hook, *rest]) + "。"

    def _rewrite_short_drama(self, text: str) -> str:
        sentences = self._plain_sentences(text)
        if not sentences:
            return text.strip()
        lines = ["【场景】人群围观，主角被迫站到风口。"]
        speakers = ["旁白", "主角", "对手"]
        for index, sentence in enumerate(sentences[:18]):
            speaker = speakers[index % len(speakers)]
            lines.append(f"{speaker}：{sentence}。")
        return "\n".join(lines)

    def _rewrite_shorts_narration(self, text: str) -> str:
        sentences = self._plain_sentences(text)
        if not sentences:
            return text.strip()
        lines = [
            f"3 秒看懂：{sentences[0]}。",
            "但真正的重点，不是表面这件事。",
        ]
        for sentence in sentences[1:10]:
            lines.append(f"{sentence}。")
        lines.append("最后这个反转，才是观众会继续看下去的原因。")
        return "\n".join(lines)

    def _rewrite_compressed(self, text: str) -> str:
        sentences = [self._trim_sentence(sentence) for sentence in self._plain_sentences(text) if sentence.strip()]
        if not sentences:
            return text.strip()
        key_sentences = sentences[:2]
        if len(sentences) > 4:
            key_sentences.extend(sentences[2::2])
        else:
            key_sentences.extend(sentences[2:])
        compressed = [sentence[:54] if len(sentence) > 54 else sentence for sentence in key_sentences[:8]]
        return "。\n".join(compressed) + "。"

    def _rewrite_plot_reframe(self, text: str) -> str:
        sentences = [self._trim_sentence(sentence) for sentence in self._plain_sentences(text) if sentence.strip()]
        if not sentences:
            return text.strip()
        frames = [
            "把冲突移到一场临时审查会上，主角的动机改成保护同伴而不是证明自己",
            "关键误会不再来自公开指责，而来自一份被调包的旧记录",
            "推进方式改成主角主动布置验证环节，让对手误以为局面仍在掌控中",
            "第一个爽点放在旁观者发现线索反常，而不是直接揭露真相",
            "反转兑现改成系统日志和第三方证词同时出现，迫使所有人重新判断",
            "结尾留下新的选择题：主角没有追求掌声，而是把决定权交给被影响的人",
        ]
        reframed: list[str] = []
        for index, frame in enumerate(frames):
            source_hint = sentences[index % len(sentences)]
            reframed.append(f"{frame}，原先的“{source_hint[:28]}”只保留情绪功能，不复用事件路径")
        return "。\n".join(reframed) + "。"

    def _plain_sentences(self, text: str) -> list[str]:
        return [item.strip() for item in re.split(r"[。！？!?\n]+", text) if item.strip()]

    def _trim_sentence(self, sentence: str) -> str:
        trimmed = re.sub(r"(其实|然后|于是|接着|这个时候|没想到|突然|立刻|马上|非常|真的|开始)", "", sentence)
        trimmed = re.sub(r"\s+", "", trimmed)
        return trimmed[:72] if len(trimmed) > 72 else trimmed

    def _report_options(self, data: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {
                "id": str(report.get("id") or ""),
                "video_title": str(report.get("video_title") or ""),
                "video_url": str(report.get("video_url") or ""),
                "created_at": str(report.get("created_at") or ""),
            }
            for report in data["reports"]
        ]

    def _idea_options(self, data: dict[str, Any]) -> list[dict[str, str]]:
        ideas: list[dict[str, str]] = []
        for idea in data["idea_cards"]:
            if isinstance(idea, dict):
                ideas.append(
                    {
                        "id": str(idea.get("id") or ""),
                        "title": str(idea.get("title") or ""),
                        "source_report_id": str(idea.get("source_report_id") or ""),
                    }
                )
        for report in data["reports"]:
            report_id = str(report.get("id") or "")
            report_ideas = report.get("idea_cards") if isinstance(report.get("idea_cards"), list) else []
            for index, idea in enumerate(report_ideas):
                if isinstance(idea, dict):
                    ideas.append(
                        {
                            "id": str(idea.get("id") or f"{report_id}-idea-{index + 1}"),
                            "title": str(idea.get("title") or ""),
                            "source_report_id": report_id,
                        }
                    )
        return ideas

    def _find_idea(self, data: dict[str, Any], idea_id: str, report_id: str) -> dict[str, Any] | None:
        if idea_id:
            for idea in data["idea_cards"]:
                if isinstance(idea, dict) and str(idea.get("id") or "") == idea_id:
                    return idea
        report = self._find_by_id(data["reports"], report_id)
        if not report:
            return None
        report_ideas = report.get("idea_cards") if isinstance(report.get("idea_cards"), list) else []
        for index, idea in enumerate(report_ideas):
            if not isinstance(idea, dict):
                continue
            normalized = {"id": idea.get("id") or f"{report_id}-idea-{index + 1}", **idea}
            if not idea_id or str(normalized.get("id") or "") == idea_id:
                return normalized
        return None

    def _find_template(self, data: dict[str, Any], template_id: str) -> dict[str, Any] | None:
        if not template_id:
            return None
        for template in data.get("favorite_structure_templates", []):
            if isinstance(template, dict) and str(template.get("id") or "") == template_id:
                return template
        raise ValueError("Structure template not found.")

    def _find_style(self, data: dict[str, Any], style_id: str) -> dict[str, Any] | None:
        if not style_id:
            return None
        for style in data.get("style_profiles", []):
            if isinstance(style, dict) and str(style.get("id") or "") == style_id:
                return style
        raise ValueError("Style profile not found.")

    def _transcript_for_report(self, report: dict[str, Any]) -> dict[str, Any] | None:
        video_id = str(report.get("youtube_video_id") or "")
        if not video_id:
            return None
        return TranscriptStore(self.settings).get_transcript(video_id)

    def _story_workbench_for_report(self, data: dict[str, Any], report_id: str) -> dict[str, Any] | None:
        for item in data["story_workbench_items"]:
            if str(item.get("report_id") or "") == report_id:
                return item
        return None

    def _clean_transcript_text(self, raw_text: str) -> str:
        text = re.sub(r"\[[^\]]+\]", " ", raw_text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return ""
        segments = re.split(r"(?<=[。！？!?])\s+", text)
        paragraphs: list[str] = []
        current: list[str] = []
        for segment in segments:
            if not segment.strip():
                continue
            current.append(segment.strip())
            if len("".join(current)) >= 120:
                paragraphs.append("".join(current))
                current = []
        if current:
            paragraphs.append("".join(current))
        return "\n".join(paragraphs)

    def _inkos_args(self, direction: str, output_type: str) -> list[str]:
        if output_type in {"short_fiction", "story_recap"}:
            return [
                "inkos",
                "short",
                "run",
                "--direction",
                direction.strip(),
                "--reference",
                "<exported-reference.md>",
                "--json",
            ]
        return [
            "inkos",
            "interact",
            "--json",
            "--message",
            f"根据创作转化参考包创作：{direction.strip()}",
        ]

    def _inkos_command(self, args: list[str]) -> str:
        return " ".join(self._quote_command_arg(arg) for arg in args)

    def _inkos_execution_args(self, project: dict[str, Any], reference_path: Path, run_dir: Path) -> list[str]:
        story_id = self._slug(str(project.get("name") or project.get("id") or "story"))[:48]
        command = self.settings.inkos_command.strip() or "inkos"
        return [
            *self._split_command(command),
            "short",
            "run",
            "--direction",
            str(project.get("direction") or ""),
            "--reference",
            str(reference_path),
            "--story-id",
            story_id or str(project.get("id") or "story"),
            "--out-dir",
            str(run_dir / "shorts"),
            "--llm-base-url",
            self._workspace_openai_base_url(),
            "--model",
            self._workspace_openai_model(),
            "--no-cover",
            "--json",
        ]

    def _split_command(self, command: str) -> list[str]:
        parts = [part for part in re.findall(r'"([^"]+)"|(\S+)', command) for part in part if part]
        return parts or ["inkos"]

    def _resolve_executable(self, executable: str) -> str:
        candidate = executable.strip().strip('"')
        if not candidate:
            return ""
        path = Path(candidate)
        if path.is_absolute() or any(separator in candidate for separator in ("/", "\\")):
            return str(path) if path.exists() else ""
        return shutil.which(candidate) or ""

    def _workspace_openai_base_url(self) -> str:
        workspace_settings = WorkspaceSettingsService(self.settings).get_private()
        return workspace_settings.openai_base_url or self.settings.openai_base_url

    def _workspace_openai_model(self) -> str:
        workspace_settings = WorkspaceSettingsService(self.settings).get_private()
        return workspace_settings.openai_analysis_model or self.settings.openai_analysis_model or self.settings.openai_translation_model

    def _inkos_env(self) -> dict[str, str]:
        workspace_settings = WorkspaceSettingsService(self.settings).get_private()
        env = dict(os.environ)
        env.setdefault("INKOS_LLM_BASE_URL", workspace_settings.openai_base_url or self.settings.openai_base_url)
        env.setdefault("INKOS_LLM_MODEL", workspace_settings.openai_analysis_model or self.settings.openai_analysis_model or self.settings.openai_translation_model)
        if workspace_settings.openai_api_key or self.settings.openai_api_key:
            env.setdefault("INKOS_LLM_API_KEY", workspace_settings.openai_api_key or self.settings.openai_api_key or "")
        return env

    def _inkos_run_dir(self, project_id: str) -> Path:
        return Path(self.settings.inkos_project_dir) / self._slug(project_id)

    def _parse_inkos_json(self, stdout: str) -> dict[str, Any]:
        text = stdout.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            matches = re.findall(r"\{[\s\S]*\}", text)
            for candidate in reversed(matches):
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    continue
        return {}

    def _inkos_draft_text(self, payload: dict[str, Any], run_dir: Path, stdout: str) -> str:
        for key in ("finalMarkdown", "markdown", "draft", "content", "text"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for key in ("finalMarkdownPath", "finalPath", "outputPath"):
            value = payload.get(key)
            if isinstance(value, str):
                candidate = Path(value)
                if not candidate.is_absolute():
                    candidate = run_dir / candidate
                if candidate.exists():
                    return candidate.read_text(encoding="utf-8").strip()
        candidates = sorted(run_dir.glob("shorts/**/final/full.md"), key=lambda item: item.stat().st_mtime, reverse=True)
        if candidates:
            return candidates[0].read_text(encoding="utf-8").strip()
        return stdout.strip()

    def _inkos_request_snapshot(
        self,
        project: dict[str, Any],
        reference_path: Path,
        reference_markdown: str,
        *,
        reference_run_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "project_id": str(project.get("id") or ""),
            "source_report_id": str(project.get("source_report_id") or ""),
            "source_video_title": str(project.get("source_video_title") or ""),
            "direction": str(project.get("direction") or ""),
            "output_type": str(project.get("output_type") or ""),
            "similarity_level": str(project.get("similarity_level") or ""),
            "target_length": str(project.get("target_length") or ""),
            "keep_narration": bool(project.get("keep_narration")),
            "reference_path": str(reference_path),
            "reference_length": len(reference_markdown),
            "reference_preview": reference_markdown[:500],
            "reference_markdown": reference_markdown,
            "reference_run_id": reference_run_id or "",
            "generation_preview": project.get("inkos_preview") if isinstance(project.get("inkos_preview"), dict) else {},
        }

    def _elapsed_ms(self, started: float) -> int:
        return max(0, int((time.monotonic() - started) * 1000))

    def _record_inkos_success(
        self,
        project_id: str,
        command: list[str],
        run_dir: Path,
        payload: dict[str, Any],
        *,
        run_id: str,
        request_snapshot: dict[str, Any],
        started_at: str,
        elapsed_ms: int,
        draft_preview: str,
        stdout: str = "",
        stderr: str = "",
    ) -> dict[str, Any]:
        holder: dict[str, Any] = {}

        def update(data: dict[str, Any]) -> None:
            project = self._find_by_id(data["imitation_projects"], project_id)
            if not project:
                return
            project["inkos_status"] = "draft_generated"
            record = {
                "id": run_id,
                "status": "complete",
                "command": command,
                "run_dir": str(run_dir),
                "request": request_snapshot,
                "result": payload,
                "draft_preview": draft_preview,
                "stdout": self._trim_process_output(stdout),
                "stderr": self._trim_process_output(stderr),
                "started_at": started_at,
                "completed_at": utc_now_iso(),
                "ran_at": started_at,
                "elapsed_ms": elapsed_ms,
            }
            self._append_inkos_run(project, record)
            holder["project"] = project

        self.store.update(update)
        return holder.get("project", {})

    def _record_inkos_failure(
        self,
        project_id: str,
        command: list[str],
        message: str,
        *,
        run_id: str,
        run_dir: Path,
        request_snapshot: dict[str, Any],
        started_at: str,
        elapsed_ms: int,
        stdout: str = "",
        stderr: str = "",
    ) -> dict[str, Any]:
        holder: dict[str, Any] = {}

        def update(data: dict[str, Any]) -> None:
            project = self._find_by_id(data["imitation_projects"], project_id)
            if not project:
                return
            project["inkos_status"] = "inkos_failed"
            record = {
                "id": run_id,
                "status": "failed",
                "command": command,
                "run_dir": str(run_dir),
                "request": request_snapshot,
                "error_message": message,
                "stdout": self._trim_process_output(stdout),
                "stderr": self._trim_process_output(stderr),
                "started_at": started_at,
                "completed_at": utc_now_iso(),
                "ran_at": started_at,
                "elapsed_ms": elapsed_ms,
            }
            self._append_inkos_run(project, record)
            holder["project"] = project

        self.store.update(update)
        if holder.get("project"):
            return holder["project"]
        return self._find_by_id(self.store.load()["imitation_projects"], project_id) or {}

    def _append_inkos_run(self, project: dict[str, Any], record: dict[str, Any]) -> None:
        project["last_inkos_run"] = record
        history = project.setdefault("inkos_run_history", [])
        if not isinstance(history, list):
            history = []
            project["inkos_run_history"] = history
        history.insert(0, record)
        del history[10:]

    def _trim_process_output(self, value: str, limit: int = 4000) -> str:
        text = value.strip()
        if len(text) <= limit:
            return text
        return text[:limit] + "\n...[truncated]"

    def _quote_command_arg(self, value: str) -> str:
        if value.startswith("<") and value.endswith(">"):
            return value
        if not value:
            return '""'
        if re.search(r'[\s"`$&|<>^]', value):
            return '"' + value.replace('"', '\\"') + '"'
        return value

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _safe_float(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    def _normalized_project_ids(self, project_ids: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for project_id in project_ids:
            value = str(project_id or "").strip()
            if not value or value in seen:
                continue
            normalized.append(value)
            seen.add(value)
        return normalized

    def _find_by_id(self, items: list[dict[str, Any]], item_id: str) -> dict[str, Any] | None:
        for item in items:
            if str(item.get("id") or "") == item_id:
                return item
        return None

    def _text(self, data: dict[str, Any], *path: str) -> str:
        current: Any = data
        for key in path:
            if not isinstance(current, dict):
                return ""
            current = current.get(key)
        return str(current or "")

    def _clean_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _dedupe_texts(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = value.strip()
            if not text or text in seen:
                continue
            deduped.append(text)
            seen.add(text)
        return deduped

    def _bullets(self, items: list[str]) -> list[str]:
        return [f"- {item}" for item in items if item]

    def _project_name(self, report: dict[str, Any], direction: str) -> str:
        title = str(report.get("video_title") or "Source").strip()
        brief = direction.strip()[:28] or "新故事方向"
        return f"{title[:28]} -> {brief}"

    def _output_label(self, output_type: str) -> str:
        labels = {
            "short_fiction": "短片小说",
            "story_recap": "故事解说文案",
            "short_drama": "短剧脚本",
            "interactive": "互动故事",
        }
        return labels.get(output_type, output_type)

    def _similarity_label(self, level: str) -> str:
        labels = {
            "low": "轻度：只保留机制",
            "medium": "中度：保留结构和节奏",
            "high": "强风格：结构、节奏和叙述口吻都贴近",
        }
        return labels.get(level, level)

    def _risk_level(self, level: str) -> str:
        if level == "high":
            return "needs_review"
        if level == "low":
            return "low"
        return "medium"

    def _draft_status(self, similarity_report: dict[str, Any] | str) -> str:
        if isinstance(similarity_report, dict):
            gate = similarity_report.get("quality_gate") if isinstance(similarity_report.get("quality_gate"), dict) else {}
            gate_status = str(gate.get("status") or "")
            if gate_status == "pass":
                return "publishable"
            if gate_status == "blocked":
                return "needs_revision"
            if gate_status == "needs_revision":
                return "needs_review"
            risk_level = str(similarity_report.get("risk_level") or "")
        else:
            risk_level = similarity_report
        if risk_level == "high":
            return "needs_revision"
        if risk_level == "medium":
            return "needs_review"
        return "publishable"

    def _can_mark_publishable(self, draft: dict[str, Any]) -> tuple[bool, str]:
        similarity_report = draft.get("similarity_report") if isinstance(draft.get("similarity_report"), dict) else {}
        risk_level = str(similarity_report.get("risk_level") or "")
        gate = similarity_report.get("quality_gate") if isinstance(similarity_report.get("quality_gate"), dict) else {}
        gate_status = str(gate.get("status") or "")
        failed_checks = {str(item) for item in gate.get("failed_checks") or []}
        hard_failures = {"text_overlap", "repeated_phrases", "reused_entities"}

        if risk_level == "high":
            return False, "high_risk"
        if gate_status == "blocked":
            return False, "quality_gate_blocked"
        if failed_checks & hard_failures:
            return False, "quality_gate_blocked"
        if gate_status and gate_status != "pass":
            return False, "quality_gate_needs_revision"
        return True, ""

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value).strip("-").lower()
        return slug[:80] or "imitation-reference"
