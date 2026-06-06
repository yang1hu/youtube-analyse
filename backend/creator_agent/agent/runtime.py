from dataclasses import dataclass
from typing import Any

from creator_agent.agent.schemas import (
    CommentInsights,
    CreatorReport,
    CreativeBreakdown,
    GrowthJudgement,
    IdeaCardArtifact,
)
from creator_agent.agent.state import AgentState
from creator_agent.tools import ToolRegistry


@dataclass
class AgentResult:
    report: CreatorReport
    tool_results: dict[str, dict]


class AgentRuntime:
    def __init__(self, tool_registry: ToolRegistry, max_steps: int = 6) -> None:
        self.tool_registry = tool_registry
        self.max_steps = max_steps

    def run_video_analysis(self, video_url: str) -> AgentResult:
        state = AgentState(target={"video_url": video_url})

        metadata = self._execute(state, "get_video_metadata", video_url=video_url)
        video_id = str(metadata.get("youtube_video_id") or metadata.get("video_id") or "")
        channel = metadata.get("channel") if isinstance(metadata.get("channel"), dict) else {}
        channel_id = str(metadata.get("channel_id") or channel.get("id") or "")

        transcript = self._execute(state, "get_transcript", video_id=video_id)
        if transcript.get("status") != "ready":
            raise RuntimeError("Transcript is not ready for analysis.")

        comments = self._execute(state, "get_comments", video_id=video_id, mode="top", limit=20)
        channel_profile = self._execute(state, "get_channel_profile", channel_id=channel_id)
        metrics = self._execute(
            state,
            "compute_video_metrics",
            video=metadata,
            channel_baseline={"avg_view_count": 0},
        )

        report = self._build_report(
            metadata=metadata,
            transcript=transcript,
            comments=comments,
            channel_profile=channel_profile,
            metrics=metrics,
        )
        return AgentResult(report=report, tool_results=state.tool_results)

    def _execute(self, state: AgentState, name: str, **kwargs: Any) -> dict[str, Any]:
        if state.step_count >= self.max_steps:
            raise RuntimeError(f"Agent exceeded max_steps={self.max_steps}.")

        state.step_count += 1
        result = self.tool_registry.execute(name, **kwargs)
        if not isinstance(result, dict):
            raise RuntimeError(f"Tool {name} returned non-dict result.")

        state.tool_results[name] = result
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
        performance_band = str(metrics.get("performance_band") or "low")
        score = self._growth_score(metrics=metrics, transcript_text=transcript_text)

        return CreatorReport(
            summary=f"{title} is a creator growth video with reusable audience-building patterns.",
            creative_breakdown=CreativeBreakdown(
                topic_type="creator_growth",
                title_hook=title,
                opening_hook="Frames a practical growth problem for creators.",
                structure=["promise", "framework", "examples", "next action"],
                emotional_curve=["curiosity", "clarity", "confidence"],
                monetization_intent=self._monetization_intent(channel_profile),
            ),
            growth_judgement=GrowthJudgement(
                score=score,
                reasons=[
                    f"Performance band is {performance_band}.",
                    "Transcript is available for extracting reusable creator tactics.",
                ],
            ),
            idea_cards=[
                IdeaCardArtifact(
                    title=f"Steal the growth loop behind: {title}",
                    angle="creator growth breakdown",
                    why_it_works="It turns a proven creator topic into a reusable framework.",
                    outline=["identify the promise", "break down the mechanism", "adapt it to a niche"],
                    risk_notes="Avoid copying the source title, examples, or unique creator positioning.",
                    score=score,
                )
            ],
            comment_insights=CommentInsights(status=self._comment_status(comments)),
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
