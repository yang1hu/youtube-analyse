from typing import Literal

from pydantic import BaseModel, Field


class CreativeBreakdown(BaseModel):
    topic_type: str
    title_hook: str
    opening_hook: str
    structure: list[str] = Field(default_factory=list)
    emotional_curve: list[str] = Field(default_factory=list)
    monetization_intent: str | None = None


class GrowthJudgement(BaseModel):
    score: int = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    channel_history_links: list[str] = Field(default_factory=list)


class IdeaCardArtifact(BaseModel):
    title: str
    angle: str
    why_it_works: str
    outline: list[str] = Field(default_factory=list)
    risk_notes: str
    score: int = Field(ge=0, le=100)


class CommentInsights(BaseModel):
    status: Literal["ok", "not_configured", "failed"] = "not_configured"
    pain_points: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    praise_points: list[str] = Field(default_factory=list)
    controversy_signals: list[str] = Field(default_factory=list)


class CreatorReport(BaseModel):
    summary: str
    creative_breakdown: CreativeBreakdown
    growth_judgement: GrowthJudgement
    idea_cards: list[IdeaCardArtifact] = Field(default_factory=list)
    comment_insights: CommentInsights = Field(default_factory=CommentInsights)
