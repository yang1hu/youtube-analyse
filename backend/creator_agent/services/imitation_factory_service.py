from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from creator_agent.config import Settings
from creator_agent.services.transcript_store import TranscriptStore
from creator_agent.services.workspace_store import WorkspaceStore, unique_workspace_id


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


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
        }

    def create_project(
        self,
        *,
        report_id: str,
        idea_id: str | None = None,
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
            transcript = self._transcript_for_report(report)
            package = self._build_reference_package(
                report=report,
                idea=idea,
                transcript=transcript,
                direction=direction,
                output_type=output_type,
                similarity_level=similarity_level,
                target_length=target_length,
                keep_narration=keep_narration,
            )
            project = {
                "id": unique_workspace_id("imitate"),
                "name": self._project_name(report, direction),
                "source_report_id": report_id,
                "source_idea_id": idea.get("id", "") if idea else "",
                "source_video_title": report.get("video_title") or "",
                "source_video_url": report.get("video_url") or "",
                "direction": direction.strip(),
                "output_type": output_type,
                "similarity_level": similarity_level,
                "target_length": target_length.strip(),
                "keep_narration": keep_narration,
                **package,
                "created_at": utc_now_iso(),
            }
            data["imitation_projects"].insert(0, project)
            holder["project"] = project

        self.store.update(create)
        return {"project": holder["project"]}

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
        direction: str,
        output_type: str,
        similarity_level: str,
        target_length: str,
        keep_narration: bool,
    ) -> dict[str, Any]:
        breakdown = report.get("creative_breakdown") if isinstance(report.get("creative_breakdown"), dict) else {}
        growth = report.get("growth_judgement") if isinstance(report.get("growth_judgement"), dict) else {}
        structure = self._clean_list(breakdown.get("structure"))
        emotional_curve = self._clean_list(breakdown.get("emotional_curve"))
        growth_reasons = self._clean_list(growth.get("reasons"))
        idea_outline = self._clean_list(idea.get("outline") if idea else [])
        raw_text = str(transcript.get("raw_text") or "") if transcript else ""
        cleaned_script = self._clean_transcript_text(raw_text)
        style_fingerprint = self._style_fingerprint(cleaned_script, breakdown, structure)
        constraints = self._constraints(similarity_level, keep_narration)
        anti_copy = self._anti_copy_rules(report, idea)

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
            direction=direction,
            output_type=output_type,
            similarity_level=similarity_level,
            target_length=target_length,
        )
        inkos_args = self._inkos_args(direction, output_type)
        inkos_command = self._inkos_command(inkos_args)
        return {
            "reference_markdown": reference_markdown,
            "inkos_command": inkos_command,
            "inkos_args": inkos_args,
            "structure_template": structure or idea_outline,
            "emotional_curve": emotional_curve,
            "style_fingerprint": style_fingerprint,
            "reuse_constraints": constraints,
            "anti_copy_rules": anti_copy,
            "source_script_excerpt": cleaned_script[:2200],
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
        direction: str,
        output_type: str,
        similarity_level: str,
        target_length: str,
    ) -> str:
        lines = [
            f"# InkOS 仿写参考包：{report.get('video_title') or 'Source video'}",
            "",
            "## 生成目标",
            f"- 输出类型：{self._output_label(output_type)}",
            f"- 新故事方向：{direction.strip()}",
            f"- 目标长度：{target_length.strip()}",
            f"- 相似强度：{self._similarity_label(similarity_level)}",
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
            "## 必须保留",
            *self._bullets(constraints),
            "",
            "## 必须改写，避免侵权或洗稿",
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
            {"key": "similarity_level", "label": "相似强度", "target": self._similarity_label(similarity_level)},
        ]

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

    def _transcript_for_report(self, report: dict[str, Any]) -> dict[str, Any] | None:
        video_id = str(report.get("youtube_video_id") or "")
        if not video_id:
            return None
        return TranscriptStore(self.settings).get_transcript(video_id)

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
            f"根据仿写参考包创作：{direction.strip()}",
        ]

    def _inkos_command(self, args: list[str]) -> str:
        return " ".join(self._quote_command_arg(arg) for arg in args)

    def _quote_command_arg(self, value: str) -> str:
        if value.startswith("<") and value.endswith(">"):
            return value
        if not value:
            return '""'
        if re.search(r'[\s"`$&|<>^]', value):
            return '"' + value.replace('"', '\\"') + '"'
        return value

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

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value).strip("-").lower()
        return slug[:80] or "imitation-reference"
