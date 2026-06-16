import json
import os
import re
import time
from typing import Any

import httpx

from creator_agent.agent.schemas import CommentInsights, CreatorReport, CreativeBreakdown, GrowthJudgement, IdeaCardArtifact
from creator_agent.config import Settings
from creator_agent.services.analysis_audit_logger import AnalysisAuditLogger
from creator_agent.services.settings_service import WorkspaceSettingsService


class LLMReportAnalyzer:
    def __init__(self, settings: Settings | None = None, audit_logger: AnalysisAuditLogger | None = None) -> None:
        self.settings = settings or Settings()
        self.workspace_settings = WorkspaceSettingsService(self.settings).get_private()
        self.audit_logger = audit_logger

    def analyze(
        self,
        *,
        metadata: dict[str, Any],
        transcript: dict[str, Any],
        comments: dict[str, Any],
        channel_profile: dict[str, Any],
        metrics: dict[str, Any],
    ) -> CreatorReport:
        model_json = self._call_model(
            self._build_payload(
                metadata=metadata,
                transcript=transcript,
                comments=comments,
                channel_profile=channel_profile,
                metrics=metrics,
            )
        )
        return self._report_from_model_json(model_json, comments=comments)

    def _build_payload(
        self,
        *,
        metadata: dict[str, Any],
        transcript: dict[str, Any],
        comments: dict[str, Any],
        channel_profile: dict[str, Any],
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        transcript_text = str(transcript.get("text") or "")
        if len(transcript_text) > 55_000:
            transcript_text = transcript_text[:55_000]

        return {
            "model": self._model(),
            "instructions": self._instructions(),
            "input": json.dumps(
                {
                    "video_metadata": metadata,
                    "transcript": {
                        "source": transcript.get("source"),
                        "language": transcript.get("language"),
                        "text": transcript_text,
                    },
                    "comments": comments,
                    "channel_profile": channel_profile,
                    "metrics": metrics,
                },
                ensure_ascii=False,
            ),
        }

    def _instructions(self) -> str:
        return (
            "你是一个面向 YouTube 创作者的资深内容分析智能体。"
            "你的任务不是复述字幕，而是抓住视频真正的点击原因、留存机制、剧情爽点和可复用模板。"
            "请用中文输出严格 JSON，不要 Markdown。"
            "必须输出字段：summary, topic_type, title_hook, opening_hook, structure, emotional_curve, "
            "growth_score, growth_reasons, idea_cards, comment_insights。"
            "字段格式要求：summary/title_hook/opening_hook/topic_type 必须是字符串；"
            "structure/emotional_curve/growth_reasons 必须是字符串数组；"
            "如果你想表达多个子点，请把它们合并成一条可读中文句子，不要返回嵌套对象。"
            "summary 要说明视频核心卖点和观众为什么会继续看；"
            "title_hook 分析标题点击钩子；opening_hook 分析前 30-60 秒如何留人；"
            "structure 给 5-8 个高层故事/内容节拍，不要摘抄原文；"
            "emotional_curve 给情绪推进；growth_reasons 解释这个视频为什么可能有效；"
            "idea_cards 给 1-3 个可复用选题卡，每项包含 title, angle, why_it_works, outline, risk_notes, score。"
            "每个 idea_card 的 outline 必须输出 6-8 步完整创作大纲，必须覆盖：标题承诺/观众期待、前 15 秒开场钩子、"
            "主角/对象/问题设定、第一冲突或信息差、中段升级点、爽点/反转/证据兑现、结尾悬念、避抄改写方向。"
            "outline 每一步必须是可执行中文句子，不要只写名词短语。"
            "如果是 Manhwa/故事解说，重点分析信息差、身份差、强制靠近、反派揭露、爽点升级和结尾悬念。"
            "comment_insights 至少包含 status；评论未采集时 status 为 not_configured。"
        )

    def _call_model(self, payload: dict[str, Any]) -> dict[str, Any]:
        api_key = self._api_key()
        if not api_key:
            raise ValueError("OPENAI_API_KEY or YCA_OPENAI_API_KEY is required for LLM analysis.")

        url = f"{self._base_url().rstrip('/')}/responses"
        if self.audit_logger:
            self.audit_logger.write("llm_request", **self.audit_logger.summarize_llm_request(url, payload))
        response = self._post_with_retries(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            payload=payload,
        )
        data = response.json()
        text = data.get("output_text")
        if not isinstance(text, str) or not text.strip():
            text = self._text_from_response_output(data)
        if not text:
            raise RuntimeError("LLM analysis response did not contain text output.")
        if self.audit_logger:
            self.audit_logger.write("llm_response", **self.audit_logger.summarize_llm_response(data, text))
        return self._loads_model_json(self._extract_json_text(text))

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
        raise RuntimeError("LLM analysis request failed after retries.")

    def _report_from_model_json(self, data: dict[str, Any], comments: dict[str, Any]) -> CreatorReport:
        idea_cards = data.get("idea_cards") if isinstance(data.get("idea_cards"), list) else []
        normalized_ideas = []
        for item in idea_cards[:3]:
            if not isinstance(item, dict):
                continue
            title = self._flatten_text(item.get("title")) or "可复用选题"
            angle = self._flatten_text(item.get("angle")) or "内容包装拆解"
            why_it_works = self._flatten_text(item.get("why_it_works")) or "基于视频脚本中的有效叙事机制。"
            risk_notes = self._flatten_text(item.get("risk_notes")) or "避免照抄原视频表达、角色名和具体桥段。"
            normalized_ideas.append(
                IdeaCardArtifact(
                    title=title,
                    angle=angle,
                    why_it_works=why_it_works,
                    outline=self._complete_idea_outline(
                        title=title,
                        angle=angle,
                        why_it_works=why_it_works,
                        outline=self._flatten_list(item.get("outline")),
                        risk_notes=risk_notes,
                    ),
                    risk_notes=risk_notes,
                    score=self._bounded_score(item.get("score"), fallback=data.get("growth_score")),
                )
            )

        if not normalized_ideas:
            normalized_ideas = [
                IdeaCardArtifact(
                    title="复用这条视频的信息差钩子",
                    angle="内容包装拆解",
                    why_it_works="信息差能让观众持续等待真相揭露。",
                    outline=self._complete_idea_outline(
                        title="复用这条视频的信息差钩子",
                        angle="内容包装拆解",
                        why_it_works="信息差能让观众持续等待真相揭露。",
                        outline=[],
                        risk_notes="避免照抄原视频表达、角色名和具体桥段。",
                    ),
                    risk_notes="避免照抄原视频表达、角色名和具体桥段。",
                    score=self._bounded_score(data.get("growth_score")),
                )
            ]

        comment_data = data.get("comment_insights") if isinstance(data.get("comment_insights"), dict) else {}
        comment_status = comment_data.get("status") or comments.get("status") or "not_configured"
        if comment_status not in {"ok", "not_configured", "failed"}:
            comment_status = "not_configured"

        return CreatorReport(
            summary=self._flatten_text(data.get("summary")),
            creative_breakdown=CreativeBreakdown(
                topic_type=self._flatten_text(data.get("topic_type")) or "video_breakdown",
                title_hook=self._flatten_text(data.get("title_hook")),
                opening_hook=self._flatten_text(data.get("opening_hook")),
                structure=self._flatten_list(data.get("structure")),
                emotional_curve=self._flatten_list(data.get("emotional_curve")),
                monetization_intent=self._flatten_optional(data.get("monetization_intent")),
            ),
            growth_judgement=GrowthJudgement(
                score=self._bounded_score(data.get("growth_score")),
                reasons=self._flatten_list(data.get("growth_reasons")),
            ),
            idea_cards=normalized_ideas,
            comment_insights=CommentInsights(status=comment_status),
        )

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
        return (
            self.workspace_settings.openai_analysis_model
            or self.settings.openai_analysis_model
            or self.workspace_settings.openai_translation_model
            or self.settings.openai_translation_model
        )

    def _base_url(self) -> str:
        return self.workspace_settings.openai_base_url or self.settings.openai_base_url

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

    def _extract_json_text(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return cleaned[start : end + 1]
        return cleaned

    def _loads_model_json(self, text: str) -> dict[str, Any]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            repaired = re.sub(r",\s*([}\]])", r"\1", text)
            data = json.loads(repaired)
        if not isinstance(data, dict):
            raise RuntimeError("LLM analysis response JSON must be an object.")
        return data

    def _flatten_optional(self, value: Any) -> str | None:
        text = self._flatten_text(value)
        return text or None

    def _flatten_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return " ".join(value.split())
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, list):
            return "；".join(self._flatten_text(item) for item in value if self._flatten_text(item))
        if isinstance(value, dict):
            parts: list[str] = []
            for key, item in value.items():
                text = self._flatten_text(item)
                if text:
                    parts.append(f"{self._label(key)}：{text}")
            return "；".join(parts)
        return str(value)

    def _flatten_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [text for item in value if (text := self._flatten_text(item))]
        text = self._flatten_text(value)
        return [text] if text else []

    def _complete_idea_outline(
        self,
        *,
        title: str,
        angle: str,
        why_it_works: str,
        outline: list[str],
        risk_notes: str,
    ) -> list[str]:
        cleaned = [item for item in outline if item.strip()]
        if len(cleaned) >= 6:
            return cleaned[:8]

        first_conflict = cleaned[0] if cleaned else why_it_works
        upgrade = cleaned[1] if len(cleaned) > 1 else "让误解、阻力或信息差继续升级，逼出主角的下一步行动。"
        payoff = cleaned[2] if len(cleaned) > 2 else "安排一次可见兑现，让观众确认这个设定真的会带来反转。"

        return [
            f"标题承诺：围绕“{title}”建立观众期待，让观众立刻知道会看到什么反差或收益。",
            f"前 15 秒开场钩子：直接呈现{angle}的最强画面，不先解释背景，先制造继续看的理由。",
            "主角/对象/问题设定：交代谁处在低位、误解、压力或未解决问题中，让观众明确代入点。",
            f"第一冲突或信息差：{first_conflict}",
            f"中段升级点：{upgrade}",
            f"爽点/反转/证据兑现：{payoff}",
            f"结尾悬念：在第一次兑现后留下更大的代价、敌人、目标或下一次触发条件，让观众想看下一段。",
            f"避抄改写方向：保留“{angle}”的机制和情绪，不复用原视频角色名、原句、连续桥段；{risk_notes}",
        ]

    def _bounded_score(self, value: Any, fallback: Any = 60) -> int:
        try:
            score = int(value if value is not None else fallback)
        except (TypeError, ValueError):
            score = 60
        return max(0, min(100, score))

    def _label(self, key: Any) -> str:
        labels = {
            "hook_core": "核心钩子",
            "click_drivers": "点击驱动",
            "weakness": "弱点",
            "first_30_60_seconds": "前30-60秒",
            "retention_mechanisms": "留存机制",
            "best_hook_moment": "最佳钩子时刻",
            "beat": "节拍",
            "name": "名称",
            "function": "作用",
            "stage": "阶段",
            "emotion": "情绪",
            "viewer_feeling": "观众感受",
            "reason": "原因",
            "detail": "细节",
        }
        return labels.get(str(key), str(key))
