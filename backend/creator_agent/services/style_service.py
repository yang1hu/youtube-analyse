import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from creator_agent.config import Settings
from creator_agent.services.settings_service import WorkspaceSettingsService
from creator_agent.services.workspace_shapes import empty_workspace_data
from creator_agent.services.workspace_store import WorkspaceStore, unique_workspace_id


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class StyleService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.workspace_settings = WorkspaceSettingsService(self.settings).get_private()
        self.path = Path(self.settings.workspace_data_path)

    def list_styles(self) -> dict[str, Any]:
        data = self._load()
        return {
            "style_profiles": data["style_profiles"],
            "copy_drafts": data["copy_drafts"],
        }

    def learn_from_latest_report(self, name: str | None = None) -> dict[str, Any]:
        style_holder: dict[str, Any] = {}

        def learn(data: dict[str, Any]) -> None:
            report = self._latest_llm_report(data)
            if not report:
                raise ValueError("No successful LLM report is available for style learning.")
            profile = self._build_style_profile(
                report=report,
                name=name or self._default_style_name(report),
            )
            data["style_profiles"].insert(0, profile)
            style_holder["profile"] = profile

        self._update(learn)
        return {"style_profile": style_holder["profile"]}

    def merge_reports(self, report_ids: list[str], name: str | None = None) -> dict[str, Any]:
        cleaned_ids = [str(item).strip() for item in report_ids if str(item).strip()]
        if len(cleaned_ids) < 2:
            raise ValueError("Select at least two reports to merge.")

        style_holder: dict[str, Any] = {}

        def merge(data: dict[str, Any]) -> None:
            reports = [report for report in data["reports"] if str(report.get("id") or "") in cleaned_ids]
            if len(reports) < 2:
                raise ValueError("At least two selected reports must exist.")
            profile = self._build_merged_report_style(
                reports=reports,
                name=name or self._merged_style_name(reports),
            )
            data["style_profiles"].insert(0, profile)
            style_holder["profile"] = profile

        self._update(merge)
        return {"style_profile": style_holder["profile"]}

    def apply_style(self, style_id: str, idea_id: str, draft_type: str = "opening_script") -> dict[str, Any]:
        data = self._load()
        style = self._find_by_id(data["style_profiles"], style_id)
        if not style:
            raise ValueError("Style profile not found.")

        ideas = self._idea_cards(data)
        idea = self._find_by_id(ideas, idea_id)
        if not idea:
            raise ValueError("Idea card not found.")

        draft = self._generate_copy_draft(
            style=style,
            idea=idea,
            draft_type=draft_type,
        )
        self._update(lambda current: current["copy_drafts"].insert(0, draft))
        return {"copy_draft": draft}

    def _build_style_profile(self, report: dict[str, Any], name: str) -> dict[str, Any]:
        breakdown = report.get("creative_breakdown") if isinstance(report.get("creative_breakdown"), dict) else {}
        growth = report.get("growth_judgement") if isinstance(report.get("growth_judgement"), dict) else {}
        structure = breakdown.get("structure") if isinstance(breakdown.get("structure"), list) else []
        emotional_curve = breakdown.get("emotional_curve") if isinstance(breakdown.get("emotional_curve"), list) else []
        growth_reasons = growth.get("reasons") if isinstance(growth.get("reasons"), list) else []

        return {
            "id": unique_workspace_id("style"),
            "name": name,
            "source_report_id": report.get("id") or "",
            "source_video_title": report.get("video_title") or "",
            "source_video_url": report.get("video_url") or "",
            "topic_type": breakdown.get("topic_type") or "video_breakdown",
            "opening_formula": breakdown.get("opening_hook") or report.get("summary") or "",
            "title_formula": breakdown.get("title_hook") or "",
            "rhythm_formula": structure[:8],
            "emotional_engine": emotional_curve[:8],
            "hook_patterns": growth_reasons[:6],
            "sentence_style": "高信息密度、短句推进、先抛反差再兑现爽点。",
            "reusable_rules": [
                "先建立强身份差或处境差，再让主角获得隐藏优势。",
                "每个段落都要有新的信息差、误会或奖励兑现。",
                "用具体金额、身份变化、公开场合打脸来放大爽感。",
                "结尾留下下一次消费、下一位关键人物或更大危机。",
            ],
            "avoid_copying": [
                "不要复用原视频角色名、地名、具体对白和连续桥段。",
                "不要只替换名词，必须重设人物关系、触发事件和场景。",
                "不要让系统奖励只停留在数字上涨，要转化成身份变化和剧情冲突。",
            ],
            "created_at": utc_now_iso(),
        }

    def _build_merged_report_style(self, reports: list[dict[str, Any]], name: str) -> dict[str, Any]:
        structures: list[str] = []
        emotional_curves: list[str] = []
        hooks: list[str] = []
        growth_reasons: list[str] = []
        avoid_copying: list[str] = [
            "不要复用任一来源视频的角色名、地名、系统名、具体对白和连续桥段。",
            "只保留共同的结构机制和情绪推进，不保留单条视频的表层事件。",
            "多来源共同出现的桥段也要迁移到新题材、新场景和新人物关系。",
        ]

        for report in reports:
            breakdown = report.get("creative_breakdown") if isinstance(report.get("creative_breakdown"), dict) else {}
            growth = report.get("growth_judgement") if isinstance(report.get("growth_judgement"), dict) else {}
            structures.extend(self._clean_list(breakdown.get("structure")))
            emotional_curves.extend(self._clean_list(breakdown.get("emotional_curve")))
            hooks.extend(self._clean_list([breakdown.get("opening_hook"), breakdown.get("title_hook"), report.get("summary")]))
            growth_reasons.extend(self._clean_list(growth.get("reasons")))

        rhythm_formula = self._dedupe(structures)[:10]
        emotional_engine = self._dedupe(emotional_curves)[:10]
        hook_patterns = self._dedupe(hooks + growth_reasons)[:10]
        return {
            "id": unique_workspace_id("style"),
            "name": name.strip() or self._merged_style_name(reports),
            "source_report_id": "",
            "source_report_ids": [str(report.get("id") or "") for report in reports],
            "source_video_title": " / ".join(str(report.get("video_title") or "") for report in reports[:3] if report.get("video_title")),
            "source_video_url": "",
            "topic_type": "multi_report_merge",
            "opening_formula": hook_patterns[0] if hook_patterns else "先抛出强后果，再补充隐藏规则和身份差。",
            "title_formula": "把共同爽点转成新题材标题：低估 -> 触发 -> 公开兑现 -> 更大悬念。",
            "rhythm_formula": rhythm_formula or ["强冲突开场", "隐藏规则出现", "第一次兑现", "公开反转", "结尾抬高代价"],
            "emotional_engine": emotional_engine or ["压迫", "好奇", "爽点兑现", "身份反转", "悬念"],
            "hook_patterns": hook_patterns,
            "sentence_style": "融合多条爆款的高信息密度口播风格；短句推进，节点清楚，每段只推进一个新信息差。",
            "reusable_rules": self._merged_reusable_rules(rhythm_formula, emotional_engine),
            "avoid_copying": avoid_copying,
            "created_at": utc_now_iso(),
        }

    def _generate_copy_draft(self, style: dict[str, Any], idea: dict[str, Any], draft_type: str) -> dict[str, Any]:
        provider = "local"
        model = "fallback"
        try:
            copy = self._call_llm_for_copy(style=style, idea=idea, draft_type=draft_type)
            provider = "openai"
            model = self._model()
        except Exception as exc:
            copy = self._fallback_copy(style=style, idea=idea, error=str(exc))

        return {
            "id": unique_workspace_id("draft"),
            "style_id": style["id"],
            "idea_id": idea["id"],
            "draft_type": draft_type,
            "title": idea.get("title") or "脚本草稿",
            "provider": provider,
            "model": model,
            "copy": copy,
            "created_at": utc_now_iso(),
        }

    def _call_llm_for_copy(self, style: dict[str, Any], idea: dict[str, Any], draft_type: str) -> str:
        api_key = self._api_key()
        if not api_key:
            raise ValueError("OPENAI_API_KEY or YCA_OPENAI_API_KEY is required for style copywriting.")

        payload = {
            "model": self._model(),
            "instructions": (
                "你是 YouTube 爆款脚本文案写手。你的任务是基于风格档案和新选题写原创中文文案，"
                "不是复写原视频。禁止使用原视频角色名、具体桥段、原句和连续情节。"
                "输出要适合视频解说口播，节奏强、信息差明确、每段都有留存钩子。"
            ),
            "input": json.dumps(
                {
                    "draft_type": draft_type,
                    "style_profile": style,
                    "idea_card": idea,
                    "requirements": [
                        "生成标题备选 3 个",
                        "生成前 60 秒口播脚本",
                        "生成 5-7 段分段脚本大纲",
                        "生成结尾悬念",
                        "附上避抄提醒",
                    ],
                },
                ensure_ascii=False,
            ),
        }
        response = self._post_with_retries(
            f"{self._base_url().rstrip('/')}/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            payload=payload,
        )
        data = response.json()
        text = data.get("output_text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        text = self._text_from_response_output(data)
        if text:
            return text
        raise RuntimeError("Style copywriting response did not contain text output.")

    def _fallback_copy(self, style: dict[str, Any], idea: dict[str, Any], error: str) -> str:
        outline = idea.get("outline") if isinstance(idea.get("outline"), list) else []
        rules = style.get("reusable_rules") if isinstance(style.get("reusable_rules"), list) else []
        opening = style.get("opening_formula") or idea.get("why_it_works") or ""
        lines = [
            "## 标题备选",
            f"1. {idea.get('title', '新选题')}，但所有人都误会了真正的赢家",
            f"2. {idea.get('title', '新选题')}，下一秒身份彻底反转",
            f"3. 当一次小小补偿触发隐藏奖励，主角被迫进入更大的局",
            "",
            "## 前 60 秒口播脚本",
            f"开场先不要解释设定，直接把主角放进最尴尬的位置：{idea.get('angle', '')}",
            f"观众第一秒要知道他被低估，第三十秒要看到隐藏优势开始启动。参考风格钩子：{opening}",
            "接着让一个看似很小的动作触发巨大后果，让旁观者误会，让主角不得不隐藏真实收益。",
            "",
            "## 分段大纲",
        ]
        for idx, item in enumerate(outline[:7], start=1):
            lines.append(f"{idx}. {item}")
        if not outline:
            lines.extend(
                [
                    "1. 建立身份差和公开压力。",
                    "2. 让关键人物无意触发奖励。",
                    "3. 用第一次兑现证明设定有效。",
                    "4. 让外界误解主角背景。",
                    "5. 安排反派公开质疑。",
                    "6. 用更大身份反转完成打脸。",
                    "7. 结尾引入下一次更高金额或更高身份的人物。",
                ]
            )
        lines.extend(
            [
                "",
                "## 结尾悬念",
                "当所有人都以为主角只是运气好时，另一个更高身份的人准备为他支付一笔天价费用，下一次返现即将失控。",
                "",
                "## 避抄提醒",
                "保留风格机制，不复用原视频角色名、具体事故、原句和连续桥段。",
            ]
        )
        if error:
            lines.append(f"\n本草稿为本地兜底生成，LLM 调用信息：{error}")
        if rules:
            lines.append("\n## 风格规则")
            lines.extend(f"- {rule}" for rule in rules[:4])
        return "\n".join(lines)

    def _idea_cards(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        ideas: list[dict[str, Any]] = []
        for report in data["reports"]:
            evidence = report.get("collection_evidence") if isinstance(report.get("collection_evidence"), dict) else {}
            if evidence.get("analysis_source") != "llm" or evidence.get("analysis_status") != "ok":
                continue
            report_ideas = report.get("idea_cards") if isinstance(report.get("idea_cards"), list) else []
            for index, idea in enumerate(report_ideas):
                if isinstance(idea, dict):
                    ideas.append(
                        {
                            "id": idea.get("id") or f"{report.get('id', 'report')}-idea-{index + 1}",
                            "source": report.get("video_title") or "Source video",
                            "source_video_url": report.get("video_url") or "",
                            "source_report_id": report.get("id") or "",
                            "analysis_source": evidence.get("analysis_source") or "",
                            **idea,
                        }
                    )
        return ideas or data["idea_cards"]

    def _latest_llm_report(self, data: dict[str, Any]) -> dict[str, Any] | None:
        for report in data["reports"]:
            evidence = report.get("collection_evidence") if isinstance(report.get("collection_evidence"), dict) else {}
            if evidence.get("analysis_source") == "llm" and evidence.get("analysis_status") == "ok":
                return report
        return None

    def _default_style_name(self, report: dict[str, Any]) -> str:
        title = str(report.get("video_title") or "爆款脚本风格")
        return f"{title[:32]} 风格"

    def _merged_style_name(self, reports: list[dict[str, Any]]) -> str:
        first_title = str(reports[0].get("video_title") or "多视频")
        return f"{first_title[:24]} 等 {len(reports)} 条融合风格"

    def _merged_reusable_rules(self, rhythm_formula: list[str], emotional_engine: list[str]) -> list[str]:
        rules = [
            "保留多条视频共同出现的开场压迫、隐藏优势、第一次兑现和公开反转机制。",
            "新故事必须替换人物身份、触发事件、场景关系和奖励表达。",
            "每 1-2 段推进一个新的信息差或爽点，避免解释性段落过长。",
            "结尾必须抬高下一个代价、敌人或奖励层级，形成续看动机。",
        ]
        if rhythm_formula:
            rules.append("参考融合节奏：" + " / ".join(rhythm_formula[:5]))
        if emotional_engine:
            rules.append("参考融合情绪：" + " / ".join(emotional_engine[:5]))
        return rules

    def _clean_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value or "").strip() else []

    def _dedupe(self, items: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for item in items:
            normalized = item.strip()
            key = normalized.lower()
            if not normalized or key in seen:
                continue
            seen.add(key)
            result.append(normalized)
        return result

    def _find_by_id(self, items: list[dict[str, Any]], item_id: str) -> dict[str, Any] | None:
        for item in items:
            if item.get("id") == item_id:
                return item
        return None

    def _load(self) -> dict[str, Any]:
        try:
            return WorkspaceStore(self.settings).load()
        except Exception:
            if not self.path.exists():
                return empty_workspace_data()
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return {**empty_workspace_data(), **data}

    def _save(self, data: dict[str, Any]) -> None:
        try:
            WorkspaceStore(self.settings).save(data)
        except Exception:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({**empty_workspace_data(), **data}, ensure_ascii=False, indent=2), encoding="utf-8")

    def _update(self, mutator) -> None:
        try:
            WorkspaceStore(self.settings).update(mutator)
        except Exception:
            data = self._load()
            mutator(data)
            self._save(data)

    def _api_key(self) -> str:
        key = (
            self.workspace_settings.openai_api_key
            or self.settings.openai_api_key
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("YCA_OPENAI_API_KEY")
            or ""
        )
        if key:
            return key
        base_url = self._base_url().lower()
        if "localhost" in base_url or "127.0.0.1" in base_url:
            return "local-dev-key"
        return ""

    def _model(self) -> str:
        return self.workspace_settings.openai_analysis_model or self.settings.openai_analysis_model or self.settings.openai_translation_model

    def _base_url(self) -> str:
        return self.workspace_settings.openai_base_url or self.settings.openai_base_url

    def _post_with_retries(self, url: str, headers: dict[str, str], payload: dict[str, Any]) -> httpx.Response:
        max_attempts = 3
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=180.0)
                if response.status_code in {408, 409, 425, 429} or 500 <= response.status_code < 600:
                    if attempt < max_attempts:
                        time.sleep(1.5 * attempt)
                        continue
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                last_error = exc
                if attempt < max_attempts:
                    time.sleep(1.5 * attempt)
                    continue
                raise
        if last_error:
            raise last_error
        raise RuntimeError("Style copywriting request failed after retries.")

    def _text_from_response_output(self, data: dict[str, Any]) -> str:
        parts: list[str] = []
        output = data.get("output")
        if not isinstance(output, list):
            return ""
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if isinstance(content_item, dict) and isinstance(content_item.get("text"), str):
                    parts.append(content_item["text"])
        return "\n".join(parts).strip()
