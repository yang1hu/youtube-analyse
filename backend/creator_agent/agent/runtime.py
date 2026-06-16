from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

from creator_agent.agent.schemas import (
    CommentInsights,
    CreatorReport,
    CreativeBreakdown,
    GrowthJudgement,
    IdeaCardArtifact,
)
from creator_agent.agent.llm_report_analyzer import LLMReportAnalyzer
from creator_agent.agent.state import AgentState
from creator_agent.agent.story_recap import analyze_story_recap
from creator_agent.services.analysis_audit_logger import AnalysisAuditLogger
from creator_agent.tools import ToolRegistry


@dataclass
class AgentResult:
    report: CreatorReport
    tool_results: dict[str, dict]


class AgentRuntime:
    def __init__(self, tool_registry: ToolRegistry, max_steps: int = 6) -> None:
        self.tool_registry = tool_registry
        self.max_steps = max_steps

    def run_video_analysis(self, video_url: str, progress_callback: Callable[[str], None] | None = None) -> AgentResult:
        state = AgentState(target={"video_url": video_url})
        audit_logger = AnalysisAuditLogger()
        audit_logger.write("analysis_started", video_url=video_url)

        self._progress(progress_callback, "metadata")
        metadata = self._execute(state, "get_video_metadata", audit_logger=audit_logger, video_url=video_url)
        video_id = str(metadata.get("youtube_video_id") or metadata.get("video_id") or "")
        channel = metadata.get("channel") if isinstance(metadata.get("channel"), dict) else {}
        channel_id = str(metadata.get("channel_id") or channel.get("id") or "")
        channel_url = str(channel.get("url") or "")

        self._progress(progress_callback, "transcript")
        transcript = self._execute(state, "get_transcript", audit_logger=audit_logger, video_id=video_id)
        if transcript.get("status") != "ready":
            audit_logger.write("analysis_failed", video_url=video_url, error="Transcript is not ready for analysis.")
            raise RuntimeError("Transcript is not ready for analysis.")

        self._progress(progress_callback, "comments")
        comments = self._execute(state, "get_comments", audit_logger=audit_logger, video_id=video_id, mode="top", limit=20)
        channel_profile = self._execute(
            state,
            "get_channel_profile",
            audit_logger=audit_logger,
            channel_id=channel_id,
            channel_url=channel_url,
        )
        metrics = self._execute(
            state,
            "compute_video_metrics",
            audit_logger=audit_logger,
            video=metadata,
            channel_baseline={"avg_view_count": 0},
        )

        self._progress(progress_callback, "llm_analysis")
        report = self._build_report_with_llm_fallback(
            state=state,
            metadata=metadata,
            transcript=transcript,
            comments=comments,
            channel_profile=channel_profile,
            metrics=metrics,
            audit_logger=audit_logger,
        )
        audit_logger.write(
            "analysis_completed",
            video_url=video_url,
            video_id=video_id,
            title=metadata.get("title"),
            analysis_source=state.tool_results.get("analyze_with_llm", {}).get("source"),
            analysis_status=state.tool_results.get("analyze_with_llm", {}).get("status"),
        )
        return AgentResult(report=report, tool_results=state.tool_results)

    def _progress(self, progress_callback: Callable[[str], None] | None, step: str) -> None:
        if progress_callback:
            progress_callback(step)

    def _execute(
        self,
        state: AgentState,
        name: str,
        audit_logger: AnalysisAuditLogger | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if state.step_count >= self.max_steps:
            raise RuntimeError(f"Agent exceeded max_steps={self.max_steps}.")

        state.step_count += 1
        if audit_logger:
            audit_logger.write("tool_started", **audit_logger.summarize_tool_request(name, kwargs))
        result = self.tool_registry.execute(name, **kwargs)
        if not isinstance(result, dict):
            raise RuntimeError(f"Tool {name} returned non-dict result.")

        state.tool_results[name] = result
        if audit_logger:
            audit_logger.write("tool_finished", **audit_logger.summarize_tool_result(name, result))
        return result

    def _build_report(
        self,
        metadata: dict[str, Any],
        transcript: dict[str, Any],
        comments: dict[str, Any],
        channel_profile: dict[str, Any],
        metrics: dict[str, Any],
    ) -> CreatorReport:
        title = str(metadata.get("title") or "Untitled video")
        transcript_text = str(transcript.get("text") or "")
        description = str(transcript.get("description") or metadata.get("description") or "")
        opening_hook = self._opening_hook(transcript_text=transcript_text, description=description)
        structure = self._content_structure(transcript_text=transcript_text, description=description)
        performance_band = str(metrics.get("performance_band") or "low")
        score = self._growth_score(metrics=metrics, transcript_text=transcript_text)
        transcript_source = str(transcript.get("source") or "unknown")
        topic_type = self._topic_type(title=title, transcript_text=transcript_text, description=description)
        story_analysis = analyze_story_recap(title, transcript_text, description) if topic_type == "story_recap" else None

        return CreatorReport(
            summary=self._summary(
                title=title,
                topic_type=topic_type,
                transcript_text=transcript_text,
                transcript_source=transcript_source,
                story_premise=story_analysis.premise if story_analysis else "",
            ),
            creative_breakdown=CreativeBreakdown(
                topic_type=topic_type,
                title_hook=title,
                opening_hook=story_analysis.premise if story_analysis else opening_hook,
                structure=self._report_structure(topic_type, structure, story_analysis),
                emotional_curve=self._emotional_curve(transcript_text, topic_type),
                monetization_intent=self._monetization_intent(channel_profile),
            ),
            growth_judgement=GrowthJudgement(
                score=score,
                reasons=self._growth_reasons(
                    topic_type=topic_type,
                    performance_band=performance_band,
                    transcript_source=transcript_source,
                    story_analysis=story_analysis,
                ),
            ),
            idea_cards=[
                IdeaCardArtifact(
                    title=self._idea_title(title=title, topic_type=topic_type),
                    angle=self._idea_angle(topic_type),
                    why_it_works=self._why_it_works(
                        transcript_text=transcript_text,
                        description=description,
                        topic_type=topic_type,
                        story_analysis=story_analysis,
                    ),
                    outline=self._idea_outline(topic_type, structure, story_analysis),
                    risk_notes="Avoid copying the source title, examples, or unique creator positioning.",
                    score=score,
                )
            ],
            comment_insights=CommentInsights(status=self._comment_status(comments)),
        )

    def _build_report_with_llm_fallback(
        self,
        state: AgentState,
        metadata: dict[str, Any],
        transcript: dict[str, Any],
        comments: dict[str, Any],
        channel_profile: dict[str, Any],
        metrics: dict[str, Any],
        audit_logger: AnalysisAuditLogger | None = None,
    ) -> CreatorReport:
        try:
            report = LLMReportAnalyzer(audit_logger=audit_logger).analyze(
                metadata=metadata,
                transcript=transcript,
                comments=comments,
                channel_profile=channel_profile,
                metrics=metrics,
            )
            state.tool_results["analyze_with_llm"] = {"status": "ok", "source": "llm"}
            if audit_logger:
                audit_logger.write("llm_analysis_finished", status="ok", source="llm")
            return report
        except Exception as exc:
            state.tool_results["analyze_with_llm"] = {
                "status": "failed",
                "source": "rule_fallback",
                "error_message": str(exc),
            }
            if audit_logger:
                audit_logger.write("llm_analysis_finished", status="failed", source="rule_fallback", error=str(exc))
            return self._build_report(
                metadata=metadata,
                transcript=transcript,
                comments=comments,
                channel_profile=channel_profile,
                metrics=metrics,
            )

    def _growth_score(self, metrics: dict[str, Any], transcript_text: str) -> int:
        score = 50
        if metrics.get("performance_band") == "high":
            score += 20
        elif metrics.get("performance_band") == "normal":
            score += 10
        if transcript_text.strip():
            score += 10
        return max(0, min(100, score))

    def _comment_status(self, comments: dict[str, Any]) -> str:
        status = comments.get("status")
        if status in {"ok", "not_configured", "failed"}:
            return str(status)
        return "failed"

    def _monetization_intent(self, channel_profile: dict[str, Any]) -> str | None:
        description = str(channel_profile.get("description") or "").lower()
        if "newsletter" in description:
            return "newsletter"
        if "course" in description:
            return "course"
        return None

    def _topic_type(self, title: str, transcript_text: str, description: str) -> str:
        text = f"{title} {transcript_text[:1000]} {description}".lower()
        story_keywords = [
            "manhwa",
            "manga",
            "manhua",
            "recap",
            "billionaire",
            "villainess",
            "reborn",
            "romance",
            "contract marriage",
            "ice queen",
        ]
        if any(keyword in text for keyword in story_keywords):
            return "story_recap"

        creator_keywords = ["creator", "channel", "growth", "audience", "newsletter", "course"]
        if any(keyword in text for keyword in creator_keywords):
            return "creator_growth"

        return "video_breakdown"

    def _summary(
        self,
        title: str,
        topic_type: str,
        transcript_text: str,
        transcript_source: str,
        story_premise: str = "",
    ) -> str:
        topic_label = topic_type.replace("_", " ")
        if topic_type == "story_recap" and story_premise:
            return f"{title} is a {topic_label} built around this core promise: {story_premise}"
        if self._has_real_transcript(transcript_text):
            return f"{title} was analyzed as a {topic_label} from {transcript_source} captions."
        return f"{title} was analyzed as a {topic_label} from available metadata because captions were unavailable."

    def _opening_hook(self, transcript_text: str, description: str) -> str:
        source = transcript_text if self._has_real_transcript(transcript_text) else description
        sentence = self._first_sentence(source)
        if sentence:
            return sentence[:220]
        return "Opening hook could not be extracted from captions."

    def _content_structure(self, transcript_text: str, description: str) -> list[str]:
        source = transcript_text if self._has_real_transcript(transcript_text) else description
        sentences = self._sentences(source)
        if len(sentences) >= 3:
            return [sentence[:120] for sentence in sentences[:4]]
        if sentences:
            return [sentence[:120] for sentence in sentences] + ["adapt the core promise to a new niche"]
        return ["title promise", "available metadata", "adapt the premise to a new niche"]

    def _report_structure(self, topic_type: str, fallback_structure: list[str], story_analysis: Any) -> list[str]:
        if topic_type != "story_recap" or story_analysis is None:
            return fallback_structure

        structure = [
            f"Premise: {story_analysis.premise}",
            f"Protagonist position: {story_analysis.protagonist}",
            f"Central conflict: {story_analysis.central_conflict}",
        ]
        structure.extend(f"Turn: {turn}" for turn in story_analysis.turning_points[:3])
        return structure[:6]

    def _emotional_curve(self, transcript_text: str, topic_type: str = "video_breakdown") -> list[str]:
        if topic_type == "story_recap":
            return ["status gap", "humiliation/tension", "forced proximity", "reveal", "romantic power shift"]

        text = transcript_text.lower()
        curve = ["curiosity"]
        if any(word in text for word in ["problem", "struggle", "failed", "betrayed", "refused"]):
            curve.append("tension")
        if any(word in text for word in ["how", "because", "therefore", "secret"]):
            curve.append("reveal")
        curve.append("resolution")
        return curve

    def _growth_reasons(
        self,
        topic_type: str,
        performance_band: str,
        transcript_source: str,
        story_analysis: Any,
    ) -> list[str]:
        if topic_type == "story_recap" and story_analysis is not None:
            reasons = [
                f"Transcript source is {transcript_source}, so story beats can be extracted from the script.",
                f"The title combines high-status fantasy and forced-proximity conflict: {story_analysis.packaging_notes[0]}",
            ]
            if story_analysis.retention_hooks:
                reasons.append(f"Retention hook: {story_analysis.retention_hooks[0]}")
            reasons.append(f"Performance band is {performance_band}.")
            return reasons

        return [
            f"Performance band is {performance_band}.",
            f"Transcript source is {transcript_source}.",
        ]

    def _why_it_works(self, transcript_text: str, description: str, topic_type: str, story_analysis: Any) -> str:
        if topic_type == "story_recap" and story_analysis is not None:
            notes = " ".join(story_analysis.packaging_notes[:2])
            return f"It packages the story around a legible fantasy conflict instead of a generic recap. {notes}"
        if self._has_real_transcript(transcript_text):
            return "It is grounded in the video's actual spoken structure instead of only title-level metadata."
        if description.strip():
            return "It uses the video's description and metadata when captions are not available."
        return "It turns the available title promise into a reusable creator experiment."

    def _idea_outline(self, topic_type: str, fallback_structure: list[str], story_analysis: Any) -> list[str]:
        if topic_type == "story_recap" and story_analysis is not None:
            opening_trigger = story_analysis.retention_hooks[0] if story_analysis.retention_hooks else story_analysis.premise
            first_turn = story_analysis.turning_points[0] if story_analysis.turning_points else story_analysis.central_conflict
            second_turn = (
                story_analysis.turning_points[1]
                if len(story_analysis.turning_points) > 1
                else "raise the cost of leaving the locked relationship"
            )
            return [
                f"Title promise: rebuild the viewer expectation around {story_analysis.premise}",
                f"Opening hook: start with the fantasy trigger before explaining context: {opening_trigger}",
                f"Character setup: establish the visible power gap through {story_analysis.protagonist}",
                f"First conflict or information gap: {story_analysis.central_conflict}",
                f"Midpoint escalation: use the first turn as a retention hook: {first_turn}",
                f"Payoff or reversal: make the hidden advantage visible while the opponent still misunderstands the protagonist.",
                f"Ending suspense: {second_turn}",
                "Rewrite direction: keep the status gap and forced-proximity mechanism, but change names, setting, dialogue, and scene order.",
            ]
        outline = list(fallback_structure[:6])
        while len(outline) < 6:
            outline.append(
                [
                    "Open with the title promise before background context.",
                    "Create a first conflict or unanswered question.",
                    "Escalate the stakes with a concrete example.",
                    "Deliver one visible payoff or practical takeaway.",
                    "Close with a stronger next question or next step.",
                    "Rewrite the source mechanism without copying the source expression.",
                ][len(outline)]
            )
        return outline[:8]

    def _idea_title(self, title: str, topic_type: str) -> str:
        if topic_type == "story_recap":
            return f"Rebuild the story hook behind: {title}"
        if topic_type == "creator_growth":
            return f"Steal the growth loop behind: {title}"
        return f"Adapt the packaging behind: {title}"

    def _idea_angle(self, topic_type: str) -> str:
        if topic_type == "story_recap":
            return "story recap packaging"
        if topic_type == "creator_growth":
            return "creator growth breakdown"
        return "video packaging breakdown"

    def _has_real_transcript(self, transcript_text: str) -> bool:
        return bool(transcript_text.strip()) and not transcript_text.startswith("Transcript unavailable.")

    def _first_sentence(self, text: str) -> str:
        sentences = self._sentences(text)
        return sentences[0] if sentences else ""

    def _sentences(self, text: str) -> list[str]:
        normalized = " ".join(text.split())
        chunks = [chunk.strip() for chunk in normalized.replace("!", ".").replace("?", ".").split(".")]
        return [chunk for chunk in chunks if len(chunk) > 20]
