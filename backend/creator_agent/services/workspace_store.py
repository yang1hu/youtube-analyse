import json
import os
import re
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from creator_agent.agent.runtime import AgentRuntime
from creator_agent.config import Settings
from creator_agent.services.sample_analysis_service import SampleAnalysisService
from creator_agent.services.database_workspace_store import DatabaseWorkspaceStore
from creator_agent.services.settings_service import WorkspaceSettingsService
from creator_agent.services.transcript_store import TranscriptStore
from creator_agent.services.workspace_shapes import empty_workspace_data
from creator_agent.tools import build_default_registry
from creator_agent.tools.channel_history import get_channel_recent_videos


_WORKSPACE_LOCKS: dict[Path, threading.RLock] = {}
_WORKSPACE_LOCKS_GUARD = threading.Lock()


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def unique_workspace_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class WorkspaceStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.path = Path(self.settings.workspace_data_path)
        self._lock = self._lock_for(self.path)
        self._database_store: DatabaseWorkspaceStore | None = None

    def load(self) -> dict[str, Any]:
        if self._use_database():
            return self._db().load()
        with self._lock:
            if not self.path.exists():
                return empty_workspace_data()
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except JSONDecodeError as exc:
                backup_path = self._backup_corrupt_workspace_file()
                raise RuntimeError(f"Workspace data file is invalid JSON. A backup was saved to {backup_path}.") from exc
            return {**empty_workspace_data(), **data}

    def save(self, data: dict[str, Any]) -> dict[str, Any]:
        if self._use_database():
            return self._db().save(data)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            normalized = {**empty_workspace_data(), **data}
            self._atomic_write_json(normalized)
            return normalized

    def load_demo_workspace(self) -> dict[str, Any]:
        now = utc_now_iso()
        demo_report_id = "demo-report-public-reversal"
        demo_project_id = "demo-imitate-public-reversal"
        demo_draft_id = "demo-draft-needs-revision"
        demo_template_id = "demo-template-public-reversal"
        demo_data = {
            "channels": [
                {
                    "id": "demo-channel-story-lab",
                    "title": "Demo Story Lab",
                    "url": "https://www.youtube.com/@demo-story-lab",
                    "subscriber_count": 128000,
                    "video_count": 3,
                    "collection_status": "ok",
                    "collection_error": "",
                    "synced_at": now,
                }
            ],
            "recent_videos": [
                {
                    "id": "demo-video-1",
                    "youtube_video_id": "demo-video-1",
                    "title": "Hidden system revenge twist story",
                    "url": "https://www.youtube.com/watch?v=demo-video-1",
                    "channel_title": "Demo Story Lab",
                    "channel_url": "https://www.youtube.com/@demo-story-lab",
                    "published_at": "1 hour ago",
                    "view_count": 92000,
                    "analysis_status": "complete",
                },
                {
                    "id": "demo-video-2",
                    "youtube_video_id": "demo-video-2",
                    "title": "Secret heir exposes the fake archive",
                    "url": "https://www.youtube.com/watch?v=demo-video-2",
                    "channel_title": "Demo Story Lab",
                    "channel_url": "https://www.youtube.com/@demo-story-lab",
                    "published_at": "today",
                    "view_count": 41000,
                    "analysis_status": "pending",
                },
                {
                    "id": "demo-video-3",
                    "youtube_video_id": "demo-video-3",
                    "title": "Ordinary vlog update",
                    "url": "https://www.youtube.com/watch?v=demo-video-3",
                    "channel_title": "Demo Story Lab",
                    "channel_url": "https://www.youtube.com/@demo-story-lab",
                    "published_at": "2 weeks ago",
                    "view_count": 800,
                    "analysis_status": "pending",
                },
            ],
            "idea_cards": [
                {
                    "id": "demo-idea-public-reversal",
                    "source": "Hidden system revenge twist story",
                    "source_video_url": "https://www.youtube.com/watch?v=demo-video-1",
                    "source_report_id": demo_report_id,
                    "title": "Public reversal after a hidden rule triggers",
                    "angle": "把职场羞辱改成夜校资格审查，保留公开误会到公开反转的结构。",
                    "why_it_works": "开场压力强，隐藏规则能制造爽点，结尾有公开兑现。",
                    "outline": ["Public pressure", "Hidden rule trigger", "Evidence reveal", "Public reversal"],
                    "risk_notes": "不要复用原视频人物、公司名、系统名和具体证据道具。",
                    "score": 88,
                }
            ],
            "reports": [
                {
                    "id": demo_report_id,
                    "youtube_video_id": "demo-video-1",
                    "video_url": "https://www.youtube.com/watch?v=demo-video-1",
                    "video_title": "Hidden system revenge twist story",
                    "channel_title": "Demo Story Lab",
                    "summary": "主角在公开场合被误解，隐藏规则触发后拿出证据，最终完成公开反转。",
                    "creative_breakdown": {
                        "topic_type": "story_recap",
                        "title_hook": "Everyone mocked her until the hidden rule activated",
                        "opening_hook": "先把主角放进公开压力场。",
                        "structure": ["Public pressure", "Hidden trigger", "Evidence reveal", "Public reversal"],
                        "emotional_curve": ["humiliation", "curiosity", "payoff", "relief"],
                    },
                    "growth_judgement": {"score": 82, "reasons": ["Strong hook", "Reusable reversal structure"]},
                    "idea_cards": [
                        {
                            "id": "demo-report-idea-1",
                            "title": "Public reversal in a new school setting",
                            "angle": "换成夜校资格审查，不复用原视频设定。",
                            "why_it_works": "公开压力和证据兑现适合短片小说。",
                            "outline": ["Pressure", "Hidden rule", "Evidence", "Reversal"],
                            "risk_notes": "必须替换人物、场景、证据和系统名。",
                            "score": 86,
                        }
                    ],
                    "comment_insights": {"status": "not_configured"},
                    "collection_evidence": {
                        "analysis_source": "demo",
                        "analysis_status": "ok",
                        "transcript_status": "ok",
                        "transcript_length": 420,
                    },
                    "created_at": now,
                }
            ],
            "story_workbench_items": [
                {
                    "report_id": demo_report_id,
                    "raw_text": "Everyone in the office laughed at the trainee. Then the hidden system rule activated. The signed file exposed the fake archive. The room went silent.",
                    "cleaned_text": "Everyone in the office laughed at the trainee.\nThe hidden system rule activated when she checked the signed file.\nThe file exposed a fake archive.\nThe room went silent as the truth reversed the scene.",
                    "cleanup_stats": {"removed_noise_count": 2, "merged_segment_count": 1, "sentence_count": 4},
                    "quality_score": 86,
                    "quality_status": "ready",
                    "analysis": {
                        "opening_5s_hook": "Public pressure starts immediately.",
                        "first_30s_retention": "A hidden rule suggests the mocked character may have leverage.",
                        "protagonist_position": "Underestimated trainee under public pressure.",
                        "status_gap": "Audience knows less than the protagonist.",
                        "first_payoff": "The rule activates and reframes the evidence.",
                        "middle_escalation": "The signed file exposes the fake archive.",
                        "opposition_design": "Opponent relies on public misunderstanding.",
                        "public_reversal": "Truth is revealed in front of everyone.",
                        "ending_suspense": "The room goes silent before the next consequence.",
                        "reusable_template": [
                            "Open with public pressure.",
                            "Trigger a hidden rule or credential.",
                            "Reveal evidence through a new object.",
                            "Let the reversal happen in public.",
                        ],
                        "non_reusable_content": [
                            "Do not reuse the trainee, office, hidden system, signed file, or fake archive.",
                        ],
                        "structure_confidence": "high",
                        "evidence": {
                            "opening_5s_hook": {
                                "excerpt": "Everyone in the office laughed at the trainee.",
                                "segment_indexes": [1],
                            }
                        },
                    },
                    "versions": [],
                    "updated_at": now,
                }
            ],
            "imitation_projects": [
                {
                    "id": demo_project_id,
                    "name": "Demo - Night school public reversal",
                    "source_report_id": demo_report_id,
                    "source_idea_id": "demo-idea-public-reversal",
                    "source_template_id": "",
                    "source_video_title": "Hidden system revenge twist story",
                    "source_video_url": "https://www.youtube.com/watch?v=demo-video-1",
                    "source_channel_title": "Demo Story Lab",
                    "source_topic_type": "story_recap",
                    "direction": "改成夜校资格审查故事，保留公开压力和公开反转机制。",
                    "output_type": "short_fiction",
                    "similarity_level": "medium",
                    "target_length": "2500 Chinese characters",
                    "keep_narration": True,
                    "source_script_excerpt": "Everyone in the office laughed at the trainee. The hidden system rule activated. The signed file exposed the fake archive.",
                    "reference_markdown": "# InkOS 创作转化参考包\n\n## 可复用结构\n- 公开压力开场\n- 隐藏规则触发\n- 证据兑现\n- 公开反转\n\n## 不可复用内容\n- 不复用原人物、办公室、隐藏系统、签字文件和假档案。\n\n## 避抄边界\n- 只保留结构功能，必须更换人物、场景、事件载体和具体表达。",
                    "structure_template": [
                        "公开压力开场",
                        "隐藏规则触发",
                        "证据兑现",
                        "公开反转",
                    ],
                    "reuse_constraints": ["更换人物、场景、道具和证据形式。"],
                    "anti_copy_rules": ["不要复用原句、专名、系统名或关键证据道具。"],
                    "inkos_status": "draft_checked",
                    "generated_drafts": [
                        {
                            "id": demo_draft_id,
                            "title": "Demo draft - needs bridge rewrite",
                            "draft_text": "夜校评审会上，所有人都质疑她的资格。她拿出一枚旧校徽，触发了档案室的隐藏规则。封存记录证明对手伪造了推荐材料。现场安静下来，刚才嘲笑她的人开始低头。",
                            "source": "demo",
                            "status": "needs_revision",
                            "similarity_report": {
                                "text_overlap_percent": 6.5,
                                "repeated_phrases": [],
                                "reused_entities": [],
                                "structure_similarity": 0.88,
                                "style_similarity": 0.72,
                                "plot_similarity": 0.91,
                                "pacing_similarity": 0.87,
                                "semantic_similarity": 0.84,
                                "risk_level": "medium",
                                "risk_segments": [
                                    {
                                        "risk_type": "semantic_plot",
                                        "severity": "medium",
                                        "action_level": "should_fix",
                                        "action_label": "建议修改",
                                        "draft_excerpt": "她拿出一枚旧校徽，触发了档案室的隐藏规则。",
                                        "source_excerpt": "The hidden system rule activated when she checked the signed file.",
                                        "matched_text": "",
                                        "draft_index": 2,
                                        "recommendation": "桥段功能接近，建议更换触发机制、证据载体和兑现方式。",
                                    }
                                ],
                                "quality_gate": {
                                    "status": "needs_revision",
                                    "passed": False,
                                    "summary": "需要修改",
                                    "target_similarity_level": "medium",
                                    "checks": [
                                        {
                                            "key": "semantic_similarity",
                                            "label": "语义桥段",
                                            "passed": False,
                                            "value": 0.84,
                                            "target": "<= 0.82",
                                        }
                                    ],
                                    "failed_checks": ["semantic_similarity"],
                                    "next_action": "重构事件载体、动机和公开反转场景。",
                                },
                                "recommendations": [
                                    "语义桥段过近：不要只替换词语，改掉事件载体、动机、兑现方式或公开反转场景。",
                                    "建议二次改写高相似段落后再进入发布前人工审稿。",
                                ],
                            },
                            "inkos_result": {
                                "provider": "demo",
                                "rewrite_count": 0,
                            },
                            "created_at": now,
                        }
                    ],
                    "latest_similarity_report": {
                        "risk_level": "medium",
                        "text_overlap_percent": 6.5,
                        "semantic_similarity": 0.84,
                        "quality_gate": {
                            "status": "needs_revision",
                            "summary": "需要修改",
                            "failed_checks": ["semantic_similarity"],
                        },
                    },
                    "similarity_report_history": [],
                    "created_at": now,
                }
            ],
            "favorite_structure_templates": [
                {
                    "id": demo_template_id,
                    "source_project_id": demo_project_id,
                    "name": "Public reversal template",
                    "source_video_title": "Hidden system revenge twist story",
                    "source_channel_title": "Demo Story Lab",
                    "source_topic_type": "story_recap",
                    "output_type": "short_fiction",
                    "structure_template": ["Public pressure", "Hidden trigger", "Evidence reveal", "Public reversal"],
                    "reuse_constraints": ["Change character identity, setting, trigger object, and evidence."],
                    "anti_copy_rules": ["Do not reuse original names, system, office, signed file, or fake archive."],
                    "tags": ["story_recap", "public_reversal"],
                    "notes": "Demo template for first-run preview.",
                    "applicable_topics": ["revenge", "secret", "system"],
                    "success_cases": ["Demo - Night school public reversal"],
                    "created_at": now,
                }
            ],
            "style_profiles": [
                {
                    "id": "demo-style-public-payoff",
                    "name": "Public payoff narration",
                    "source_report_id": demo_report_id,
                    "source_video_title": "Hidden system revenge twist story",
                    "topic_type": "story_recap",
                    "opening_formula": "先把主角放进公开压力，再延迟解释底牌。",
                    "rhythm_formula": ["短句开场", "隐藏信息延迟", "公开反转收束"],
                    "reusable_rules": ["保留压力-触发-兑现-反转节奏"],
                    "avoid_copying": ["不要复用原专名、证据道具和具体台词"],
                    "created_at": now,
                }
            ],
        }

        def update(data: dict[str, Any]) -> None:
            for key, demo_items in demo_data.items():
                existing = data.setdefault(key, [])
                if not isinstance(existing, list):
                    existing = []
                    data[key] = existing
                cleaned = [
                    item
                    for item in existing
                    if not (isinstance(item, dict) and str(item.get("id") or item.get("report_id") or "").startswith("demo-"))
                ]
                data[key] = list(demo_items) + cleaned

        data, _ = self.update(update)
        return {"dashboard": self.dashboard(), "workspace": data}

    def update(self, mutator: Callable[[dict[str, Any]], Any]) -> tuple[dict[str, Any], Any]:
        if self._use_database():
            data = self.load()
            result = mutator(data)
            return self.save(data), result
        with self._lock:
            if self.path.exists():
                try:
                    data = json.loads(self.path.read_text(encoding="utf-8"))
                except JSONDecodeError as exc:
                    backup_path = self._backup_corrupt_workspace_file()
                    raise RuntimeError(f"Workspace data file is invalid JSON. A backup was saved to {backup_path}.") from exc
            else:
                data = empty_workspace_data()
            normalized = {**empty_workspace_data(), **data}
            result = mutator(normalized)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_write_json(normalized)
            return normalized, result

    def _atomic_write_json(self, data: dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        temp_path = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        temp_path.write_text(payload, encoding="utf-8")
        temp_path.replace(self.path)

    def _backup_corrupt_workspace_file(self) -> Path:
        backup_path = self.path.with_name(f"{self.path.name}.corrupt-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}")
        self.path.replace(backup_path)
        return backup_path

    def _use_database(self) -> bool:
        if os.getenv("YCA_WORKSPACE_DATA_PATH"):
            return False
        return bool(self.settings.database_url)

    def _db(self) -> DatabaseWorkspaceStore:
        if self._database_store is None:
            self._database_store = DatabaseWorkspaceStore(self.settings)
        return self._database_store

    def _lock_for(self, path: Path) -> threading.RLock:
        resolved = path.resolve()
        with _WORKSPACE_LOCKS_GUARD:
            if resolved not in _WORKSPACE_LOCKS:
                _WORKSPACE_LOCKS[resolved] = threading.RLock()
            return _WORKSPACE_LOCKS[resolved]

    def dashboard(self) -> dict[str, Any]:
        data = self.load()
        workspace_settings = WorkspaceSettingsService(self.settings).get()
        channels = data["channels"]
        recent_videos = data["recent_videos"]
        configured_urls = self._configured_channel_urls(workspace_settings)
        if configured_urls:
            channel_by_url = {str(channel.get("url") or ""): channel for channel in channels}
            configured_channels = []
            for channel_url in configured_urls:
                configured_channel = channel_by_url.get(channel_url)
                channel_title = channel_url.rstrip("/").split("/")[-1]
                configured_channels.append(
                    {
                        "id": channel_url,
                        "title": configured_channel.get("title") if configured_channel else channel_title,
                        "url": channel_url,
                        "subscriber_count": configured_channel.get("subscriber_count", 0) if configured_channel else 0,
                        "video_count": configured_channel.get("video_count", 0) if configured_channel else 0,
                        "collection_status": configured_channel.get("collection_status", "configured") if configured_channel else "configured",
                        "collection_error": configured_channel.get("collection_error", "") if configured_channel else "",
                        "synced_at": configured_channel.get("synced_at", "") if configured_channel else "",
                    }
                )
            channels = configured_channels
            configured_titles = {str(channel.get("title") or "") for channel in configured_channels}
            recent_videos = [
                video
                for video in recent_videos
                if str(video.get("channel_url") or "") in configured_urls
                or str(video.get("channel_title") or "") in configured_titles
            ]
        return {
            "channels": channels,
            "recent_videos": recent_videos,
            "topic_candidates": self._topic_candidates(recent_videos),
            "idea_cards": data["idea_cards"],
            "jobs": data["jobs"],
            "comment_collector_status": "not_configured",
            "reports_count": len(data["reports"]),
            "imitation_projects_count": len(data["imitation_projects"]),
            "pending_drafts_count": self._pending_drafts_count(data["imitation_projects"]),
            "publishable_drafts_count": self._publishable_drafts_count(data["imitation_projects"]),
            "favorite_structure_templates": self._favorite_structure_templates_with_metrics(
                data["favorite_structure_templates"],
                data["imitation_projects"],
            ),
            "imitation_project_summaries": self._imitation_project_summaries(
                data["imitation_projects"],
                data["favorite_structure_templates"],
            ),
            "creation_pipeline": self._creation_pipeline(
                channels=channels,
                recent_videos=recent_videos,
                reports=data["reports"],
                story_workbench_items=data["story_workbench_items"],
                projects=data["imitation_projects"],
                jobs=data["jobs"],
            ),
            "creation_quality_metrics": self._creation_quality_metrics(data["imitation_projects"]),
            "creation_funnel": self._creation_funnel(
                recent_videos=recent_videos,
                reports=data["reports"],
                projects=data["imitation_projects"],
            ),
            "weekly_production_metrics": self._weekly_production_metrics(
                reports=data["reports"],
                projects=data["imitation_projects"],
            ),
        }

    def sync_channel(self) -> dict[str, Any]:
        workspace_settings = WorkspaceSettingsService(self.settings).get()
        channel_urls = self._configured_channel_urls(workspace_settings)
        if not channel_urls:
            raise ValueError("Channel URL is required before syncing.")

        data = self.load()
        synced_at = utc_now_iso()
        existing_videos = [
            video
            for video in data["recent_videos"]
            if str(video.get("channel_url") or "") not in channel_urls
        ]
        synced_channels: list[dict[str, Any]] = []
        synced_videos: list[dict[str, Any]] = []

        for channel_url in channel_urls:
            channel_title = channel_url.rstrip("/").split("/")[-1]
            try:
                collection = get_channel_recent_videos(channel_id=channel_title, channel_url=channel_url)
                videos = [
                    {
                        "id": item.get("youtube_video_id") or item.get("id") or item.get("url"),
                        "youtube_video_id": item.get("youtube_video_id") or item.get("id"),
                        "title": item.get("title") or "Untitled video",
                        "url": item.get("url") or "",
                        "channel_title": channel_title,
                        "channel_url": channel_url,
                        "published_text": item.get("published_text") or "",
                        "published_at": item.get("published_text") or "",
                        "view_count": item.get("view_count") or 0,
                        "analysis_status": self._video_analysis_status(data, item.get("url") or ""),
                    }
                    for item in collection.get("videos", [])
                ]
                collection_status = collection.get("collection_status", "ok")
                collection_error = collection.get("collection_error", "")
            except Exception as exc:
                videos = [
                    video
                    for video in data["recent_videos"]
                    if str(video.get("channel_url") or "") == channel_url
                    or str(video.get("channel_title") or "") == channel_title
                ]
                collection_status = "failed"
                collection_error = str(exc)

            channel = {
                "id": channel_url,
                "title": channel_title,
                "url": channel_url,
                "subscriber_count": 0,
                "video_count": len(videos),
                "collection_status": collection_status,
                "collection_error": collection_error,
                "synced_at": synced_at,
            }
            synced_channels.append(channel)
            synced_videos.extend(videos)

        existing_channels = [
            channel
            for channel in data["channels"]
            if str(channel.get("url") or "") not in channel_urls
        ]
        data["channels"] = synced_channels + existing_channels
        data["recent_videos"] = self._dedupe_videos(synced_videos + existing_videos)
        self.save(data)
        return {
            "channel": synced_channels[0] if synced_channels else None,
            "channels": synced_channels,
            "videos": synced_videos,
        }

    def analyze_video(self, video_url: str, progress_callback: Callable[[str], None] | None = None) -> dict[str, Any]:
        job = {
            "id": unique_workspace_id("job"),
            "kind": "video_analysis",
            "status": "running",
            "target_url": video_url,
            "created_at": utc_now_iso(),
            "updated_at": utc_now_iso(),
        }

        def save_started(data: dict[str, Any]) -> None:
            data["jobs"].insert(0, job)

        self.update(save_started)

        try:
            result = AgentRuntime(build_default_registry()).run_video_analysis(video_url, progress_callback=progress_callback)
            metadata = result.tool_results.get("get_video_metadata", {})
            transcript = result.tool_results.get("get_transcript", {})
            video_id = str(metadata.get("youtube_video_id") or metadata.get("video_id") or "")
            if video_id and transcript.get("text"):
                TranscriptStore(self.settings).save_transcript(
                    video_id=video_id,
                    video_url=video_url,
                    title=str(metadata.get("title") or ""),
                    source=str(transcript.get("source") or ""),
                    language=str(transcript.get("language") or ""),
                    raw_text=str(transcript.get("text") or ""),
                )
            report_json = result.report.model_dump()
            report = {
                "id": unique_workspace_id("report"),
                "youtube_video_id": video_id,
                "video_url": video_url,
                "video_title": metadata.get("title") or report_json["creative_breakdown"]["title_hook"],
                "channel_title": (metadata.get("channel") or {}).get("title") or "",
                "summary": report_json["summary"],
                "creative_breakdown": report_json["creative_breakdown"],
                "growth_judgement": report_json["growth_judgement"],
                "idea_cards": report_json["idea_cards"],
                "comment_insights": report_json["comment_insights"],
                "collection_evidence": self._collection_evidence(result.tool_results),
                "created_at": utc_now_iso(),
            }
            if progress_callback:
                progress_callback("save_report")
            idea_cards = [
                {
                    "id": unique_workspace_id("idea"),
                    "source": report["video_title"],
                    "source_video_url": video_url,
                    **idea,
                }
                for idea in report_json["idea_cards"]
            ]

            job["status"] = "complete"
            job["current_step"] = "complete"
            job["report_id"] = report["id"]
            job["updated_at"] = utc_now_iso()

            def save_success(data: dict[str, Any]) -> None:
                for stored_job in data["jobs"]:
                    if str(stored_job.get("id") or "") == job["id"]:
                        stored_job.update(job)
                        break
                else:
                    data["jobs"].insert(0, job)
                data["reports"].insert(0, report)
                data["idea_cards"] = idea_cards + data["idea_cards"]
                self._mark_video_analyzed(data, video_url)

            self.update(save_success)
            return {"job": job, "report": report, "idea_cards": idea_cards}
        except Exception as exc:
            job["status"] = "failed"
            job["current_step"] = "failed"
            job["error_message"] = str(exc)
            job["updated_at"] = utc_now_iso()

            def save_failure(data: dict[str, Any]) -> None:
                for stored_job in data["jobs"]:
                    if str(stored_job.get("id") or "") == job["id"]:
                        stored_job.update(job)
                        return
                data["jobs"].insert(0, job)

            self.update(save_failure)
            return {"job": job, "error": str(exc)}

    def latest_report(self) -> dict[str, Any] | None:
        reports = self.reports()
        return reports[0] if reports else None

    def reports(self) -> list[dict[str, Any]]:
        data = self.load()
        return [self._enrich_report(report, data) for report in data["reports"]]

    def sample_analyses(self) -> list[dict[str, Any]]:
        return self.load()["sample_analyses"]

    def create_sample_analysis(self, video_url: str, video_title: str = "", video_id: str = "") -> dict[str, Any]:
        data = self.load()
        result = SampleAnalysisService(self.settings).analyze_video_opening(
            video_url=video_url,
            video_title=video_title,
            video_id=video_id,
        )
        data["sample_analyses"] = [
            sample for sample in data["sample_analyses"] if sample.get("id") != result.get("id")
        ]
        data["sample_analyses"].insert(0, result)
        self.save(data)
        return result

    def report_by_id(self, report_id: str) -> dict[str, Any] | None:
        data = self.load()
        for report in data["reports"]:
            if str(report.get("id") or "") == report_id:
                return self._enrich_report(report, data)
        return None

    def ideas(self) -> list[dict[str, Any]]:
        data = self.load()
        report_ideas = self._llm_report_ideas(data)
        if report_ideas:
            return report_ideas
        return data["idea_cards"]

    def prune_stale_ideas(self) -> dict[str, Any]:
        data = self.load()
        before_count = len(data["idea_cards"])
        data["idea_cards"] = self._llm_report_ideas(data)
        self.save(data)
        return {
            "before_count": before_count,
            "after_count": len(data["idea_cards"]),
            "removed_count": max(0, before_count - len(data["idea_cards"])),
            "idea_cards": data["idea_cards"],
        }

    def _llm_report_ideas(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        report_ideas: list[dict[str, Any]] = []
        for report in data["reports"]:
            evidence = report.get("collection_evidence") if isinstance(report.get("collection_evidence"), dict) else {}
            if evidence.get("analysis_source") != "llm" or evidence.get("analysis_status") != "ok":
                continue
            ideas = report.get("idea_cards") if isinstance(report.get("idea_cards"), list) else []
            for index, idea in enumerate(ideas):
                if not isinstance(idea, dict):
                    continue
                report_ideas.append(
                    {
                        "id": idea.get("id") or f"{report.get('id', 'report')}-idea-{index + 1}",
                        "source": report.get("video_title") or "Source video",
                        "source_video_url": report.get("video_url") or "",
                        "source_report_id": report.get("id") or "",
                        "analysis_source": evidence.get("analysis_source") or "",
                        "analysis_status": evidence.get("analysis_status") or "",
                        **idea,
                        "score": self._normalized_score(idea.get("score")),
                    }
                )
        return report_ideas

    def _normalized_score(self, value: Any) -> int:
        try:
            score = int(value)
        except (TypeError, ValueError):
            return 60
        if 0 < score <= 10:
            score *= 10
        return max(0, min(100, score))

    def _video_analysis_status(self, data: dict[str, Any], video_url: str) -> str:
        if any(report.get("video_url") == video_url for report in data["reports"]):
            return "complete"
        return "pending"

    def _mark_video_analyzed(self, data: dict[str, Any], video_url: str) -> None:
        for video in data["recent_videos"]:
            if video.get("url") == video_url:
                video["analysis_status"] = "complete"

    def _configured_channel_urls(self, workspace_settings: Any) -> list[str]:
        urls = list(getattr(workspace_settings, "channel_urls", []) or [])
        legacy_url = str(getattr(workspace_settings, "channel_url", "") or "")
        if legacy_url and legacy_url not in urls:
            urls.insert(0, legacy_url)
        return urls

    def _pending_drafts_count(self, projects: list[dict[str, Any]]) -> int:
        return sum(
            1
            for project in projects
            for draft in project.get("generated_drafts", [])
            if str(draft.get("status") or "") in {"needs_review", "needs_revision"}
        )

    def _publishable_drafts_count(self, projects: list[dict[str, Any]]) -> int:
        return sum(
            1
            for project in projects
            for draft in project.get("generated_drafts", [])
            if str(draft.get("status") or "") == "publishable"
        )

    def _creation_pipeline(
        self,
        *,
        channels: list[dict[str, Any]],
        recent_videos: list[dict[str, Any]],
        reports: list[dict[str, Any]],
        story_workbench_items: list[dict[str, Any]],
        projects: list[dict[str, Any]],
        jobs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        pending_videos = [
            video
            for video in recent_videos
            if str(video.get("url") or "") and str(video.get("analysis_status") or "pending") != "complete"
        ]
        active_jobs = [job for job in jobs if str(job.get("status") or "") not in {"complete", "failed"}]
        pending_drafts = self._pending_drafts_count(projects)
        publishable_drafts = self._publishable_drafts_count(projects)
        cleaned_story_count = self._cleaned_story_workbench_count(reports, story_workbench_items)
        structured_story_count = self._structured_story_workbench_count(reports, story_workbench_items)
        steps = [
            self._pipeline_step("settings", bool(channels), len(channels), "settings"),
            self._pipeline_step("sync", bool(recent_videos), len(recent_videos), "sync"),
            self._pipeline_step("analyze", bool(reports), len(reports), "video-report"),
            self._pipeline_step("clean_script", cleaned_story_count > 0, cleaned_story_count, "video-report"),
            self._pipeline_step("story_structure", structured_story_count > 0, structured_story_count, "video-report"),
            self._pipeline_step("imitation_factory", bool(projects), len(projects), "imitation-factory"),
            self._pipeline_step(
                "quality_check",
                pending_drafts == 0 and publishable_drafts > 0,
                pending_drafts + publishable_drafts,
                "imitation-factory",
            ),
            self._pipeline_step("export_publish", publishable_drafts > 0, publishable_drafts, "project-library"),
        ]

        if projects and pending_drafts:
            next_step = "quality_check"
        elif projects:
            next_step = "export_publish" if publishable_drafts else "quality_check"
        elif structured_story_count:
            next_step = "imitation_factory"
        elif cleaned_story_count:
            next_step = "story_workbench"
        elif reports:
            next_step = "clean_script"
        elif pending_videos:
            next_step = "analyze"
        elif recent_videos:
            next_step = "analyze"
        elif channels:
            next_step = "sync"
        else:
            next_step = "settings"

        return {
            "steps": steps,
            "next_step": next_step,
            "next_action": self._pipeline_next_action(next_step),
            "pending_video_count": len(pending_videos),
            "active_job_count": len(active_jobs),
            "ready_report_count": len(reports),
            "cleaned_story_count": cleaned_story_count,
            "structured_story_count": structured_story_count,
            "project_count": len(projects),
            "pending_draft_count": pending_drafts,
            "publishable_draft_count": publishable_drafts,
        }

    def _pipeline_next_action(self, next_step: str) -> dict[str, str]:
        actions = {
            "settings": {
                "label": "配置频道",
                "description": "先保存 YouTube 频道地址，系统才能同步候选素材。",
                "target_view": "settings",
                "action_type": "open_view",
            },
            "sync": {
                "label": "同步频道视频",
                "description": "拉取最新视频，形成可筛选的故事素材池。",
                "target_view": "dashboard",
                "action_type": "sync_channel",
            },
            "analyze": {
                "label": "分析候选视频",
                "description": "选择一个候选视频生成报告、字幕证据和选题卡。",
                "target_view": "video-report",
                "action_type": "open_view",
            },
            "clean_script": {
                "label": "清洗故事原文",
                "description": "进入报告页校对字幕，保存可用于结构拆解的干净文案。",
                "target_view": "video-report",
                "action_type": "open_view",
            },
            "story_workbench": {
                "label": "拆解故事结构",
                "description": "补齐钩子、爽点、反转、不可复用内容和原文证据。",
                "target_view": "video-report",
                "action_type": "open_view",
            },
            "imitation_factory": {
                "label": "生成创作包",
                "description": "把结构拆解转成 InkOS 可执行的原创转化参考包。",
                "target_view": "imitation-factory",
                "action_type": "open_view",
            },
            "quality_check": {
                "label": "质检并改写",
                "description": "检查文本重合、设定复用和语义桥段风险，必要时生成改写版本。",
                "target_view": "imitation-factory",
                "action_type": "open_view",
            },
            "export_publish": {
                "label": "导出或沉淀模板",
                "description": "导出可发布稿件，或把高质量结构收藏成可复用模板。",
                "target_view": "project-library",
                "action_type": "open_view",
            },
        }
        return actions.get(next_step, actions["export_publish"])

    def _topic_candidates(self, recent_videos: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
        candidates = []
        for video in recent_videos:
            if not str(video.get("url") or ""):
                continue
            if str(video.get("analysis_status") or "pending") == "complete":
                continue
            score, reasons = self._topic_candidate_score(video)
            views = self._as_int(video.get("view_count"))
            published = str(video.get("published_at") or video.get("published_text") or "")
            dimensions = self._topic_candidate_dimensions(video, views, published)
            recommendation = self._topic_candidate_recommendation(score, dimensions)
            candidates.append(
                {
                    "id": str(video.get("id") or video.get("youtube_video_id") or video.get("url") or ""),
                    "youtube_video_id": str(video.get("youtube_video_id") or ""),
                    "title": str(video.get("title") or "Untitled video"),
                    "url": str(video.get("url") or ""),
                    "channel_title": str(video.get("channel_title") or ""),
                    "channel_url": str(video.get("channel_url") or ""),
                    "published_at": published,
                    "view_count": views,
                    "analysis_status": str(video.get("analysis_status") or "pending"),
                    "score": score,
                    "reasons": reasons,
                    **dimensions,
                    **recommendation,
                    "topic_group": self._topic_group(video),
                    "freshness_bucket": self._freshness_bucket(published),
                    "view_bucket": self._view_bucket(views),
                }
            )
        return sorted(candidates, key=lambda item: (-item["score"], -item["view_count"], item["title"]))[:limit]

    def _topic_candidate_score(self, video: dict[str, Any]) -> tuple[int, list[str]]:
        title = str(video.get("title") or "")
        published = str(video.get("published_at") or video.get("published_text") or "")
        views = self._as_int(video.get("view_count"))
        score = 30
        reasons: list[str] = []
        if views >= 100000:
            score += 35
            reasons.append("High view count")
        elif views >= 10000:
            score += 22
            reasons.append("Above-average view count")
        elif views >= 1000:
            score += 10
            reasons.append("Early traction")
        story_keywords = ["story", "recap", "revenge", "twist", "system", "secret", "反转", "故事", "系统", "打脸", "复仇", "隐藏", "逆袭"]
        matched = [keyword for keyword in story_keywords if keyword.lower() in title.lower()]
        if matched:
            score += min(24, 8 * len(matched))
            reasons.append("Story keywords: " + ", ".join(matched[:3]))
        if any(token in published.lower() for token in ["hour", "today", "minute", "刚刚", "小时", "今天"]):
            score += 12
            reasons.append("Fresh upload")
        return min(score, 100), reasons or ["Pending analysis"]

    def _topic_candidate_dimensions(self, video: dict[str, Any], views: int, published: str) -> dict[str, Any]:
        title = str(video.get("title") or "")
        topic_group = self._topic_group(video)
        viral_potential = 30
        if views >= 100000:
            viral_potential = 92
        elif views >= 10000:
            viral_potential = 78
        elif views >= 1000:
            viral_potential = 58
        if self._freshness_bucket(published) == "fresh":
            viral_potential = min(100, viral_potential + 12)
        story_fit = 42
        if topic_group != "general":
            story_fit += 28
        story_terms = ["story", "recap", "revenge", "twist", "system", "secret", "反转", "故事", "系统", "打脸", "复仇", "隐藏", "逆袭"]
        matched_story_terms = [term for term in story_terms if term.lower() in title.lower()]
        story_fit = min(100, story_fit + min(24, len(matched_story_terms) * 8))
        reusable_structure_value = min(100, 36 + (22 if topic_group in {"revenge", "system", "secret", "twist"} else 0) + (18 if views >= 10000 else 0) + (12 if self._freshness_bucket(published) != "older" else 0))
        risk_flags: list[str] = []
        if topic_group == "general":
            risk_flags.append("题材信号弱，可能不适合短片小说结构拆解。")
        if views < 1000:
            risk_flags.append("播放表现偏低，建议降低优先级。")
        if any(token in title.lower() for token in ["full movie", "episode", "official", "clip", "完整版", "第", "集"]):
            risk_flags.append("可能是长剧/片段内容，拆解前确认版权和完整语境。")
        if any(token in title.lower() for token in ["celebrity", "real story", "真实", "明星"]):
            risk_flags.append("可能涉及真人或真实事件，转化时避免复用身份和具体经历。")
        return {
            "viral_potential": viral_potential,
            "story_fit": story_fit,
            "structure_reuse_value": reusable_structure_value,
            "risk_flags": risk_flags or ["暂无明显候选风险。"],
        }

    def _topic_candidate_recommendation(self, score: int, dimensions: dict[str, Any]) -> dict[str, str]:
        viral = self._as_int(dimensions.get("viral_potential"))
        story_fit = self._as_int(dimensions.get("story_fit"))
        structure_value = self._as_int(dimensions.get("structure_reuse_value"))
        risk_flags = [str(item) for item in dimensions.get("risk_flags") or [] if str(item).strip()]
        has_material_risk = any("copyright" in flag.lower() or "real" in flag.lower() or "真人" in flag for flag in risk_flags)
        if score >= 80 and story_fit >= 80 and structure_value >= 75 and not has_material_risk:
            return {
                "recommendation_summary": "优先分析：热度、故事适配和结构复用价值都较高，适合进入拆解队列。",
                "recommended_action": "加入批量分析，并优先在故事工坊沉淀结构模板。",
                "recommendation_level": "priority",
            }
        if story_fit >= 70 and structure_value >= 65:
            return {
                "recommendation_summary": "可以试跑：题材适合短片小说，但需要先确认字幕质量和具体设定风险。",
                "recommended_action": "先分析单条视频，检查原文证据后再决定是否批量扩展。",
                "recommendation_level": "trial",
            }
        if viral >= 70 and story_fit < 70:
            return {
                "recommendation_summary": "热度不错但故事信号偏弱，可能更适合作为选题观察样本。",
                "recommended_action": "先做样本分析或降低优先级，避免直接进入创作转化。",
                "recommendation_level": "watch",
            }
        return {
            "recommendation_summary": "暂不优先：热度、故事适配或结构复用价值不足。",
            "recommended_action": "继续观察，优先处理更高分候选视频。",
            "recommendation_level": "low",
        }

    def _topic_group(self, video: dict[str, Any]) -> str:
        title = str(video.get("title") or "").lower()
        if any(token in title for token in ["revenge", "复仇", "打脸", "逆袭"]):
            return "revenge"
        if any(token in title for token in ["system", "系统", "reward", "奖励"]):
            return "system"
        if any(token in title for token in ["secret", "hidden", "隐藏", "秘密"]):
            return "secret"
        if any(token in title for token in ["twist", "反转"]):
            return "twist"
        if any(token in title for token in ["story", "recap", "故事"]):
            return "story"
        return "general"

    def _freshness_bucket(self, published: str) -> str:
        normalized = published.lower()
        if any(token in normalized for token in ["minute", "hour", "today", "刚刚", "分钟", "小时", "今天"]):
            return "fresh"
        if any(token in normalized for token in ["day", "yesterday", "天", "昨天"]):
            return "recent"
        return "older"

    def _view_bucket(self, views: int) -> str:
        if views >= 100000:
            return "viral"
        if views >= 10000:
            return "rising"
        if views >= 1000:
            return "early"
        return "low"

    def _as_int(self, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _cleaned_story_workbench_count(
        self,
        reports: list[dict[str, Any]],
        story_workbench_items: list[dict[str, Any]],
    ) -> int:
        report_ids = {str(report.get("id") or "") for report in reports}
        return sum(
            1
            for item in story_workbench_items
            if str(item.get("report_id") or "") in report_ids and bool(str(item.get("cleaned_text") or "").strip())
        )

    def _structured_story_workbench_count(
        self,
        reports: list[dict[str, Any]],
        story_workbench_items: list[dict[str, Any]],
    ) -> int:
        report_ids = {str(report.get("id") or "") for report in reports}
        structure_fields = {
            "opening_5s_hook",
            "first_30s_retention",
            "protagonist_position",
            "status_gap",
            "first_payoff",
            "middle_escalation",
            "opposition_design",
            "public_reversal",
            "ending_suspense",
        }
        return sum(
            1
            for item in story_workbench_items
            if str(item.get("report_id") or "") in report_ids
            and isinstance(item.get("analysis"), dict)
            and any(str(item["analysis"].get(field) or "").strip() for field in structure_fields)
        )

    def _pipeline_step(self, key: str, complete: bool, count: int, action: str) -> dict[str, Any]:
        return {
            "key": key,
            "status": "complete" if complete else "pending",
            "count": count,
            "action": action,
        }

    def _creation_quality_metrics(self, projects: list[dict[str, Any]]) -> dict[str, Any]:
        drafts: list[dict[str, Any]] = []
        for project in projects:
            for draft in project.get("generated_drafts", []):
                if isinstance(draft, dict):
                    drafts.append(draft)
        if not drafts:
            return {
                "draft_count": 0,
                "quality_gate_pass_rate": 0,
                "average_text_overlap_percent": 0,
                "average_rewrite_count": 0,
                "high_risk_rate": 0,
                "failed_gate_reasons": [],
            }

        pass_count = 0
        high_risk_count = 0
        overlap_values: list[float] = []
        rewrite_count = 0
        failed_reasons: dict[str, dict[str, Any]] = {}
        for draft in drafts:
            report = draft.get("similarity_report") if isinstance(draft.get("similarity_report"), dict) else {}
            quality_gate = report.get("quality_gate") if isinstance(report.get("quality_gate"), dict) else {}
            if str(quality_gate.get("status") or "") == "pass":
                pass_count += 1
            else:
                self._add_failed_gate_reasons(failed_reasons, quality_gate)
            if str(report.get("risk_level") or "") == "high":
                high_risk_count += 1
            try:
                overlap_values.append(float(report.get("text_overlap_percent") or 0))
            except (TypeError, ValueError):
                overlap_values.append(0)
            inkos_result = draft.get("inkos_result") if isinstance(draft.get("inkos_result"), dict) else {}
            if inkos_result.get("parent_draft_id") or str(draft.get("source") or "").startswith(("rewrite_", "risk_")):
                rewrite_count += 1

        project_count = len(projects) or 1
        return {
            "draft_count": len(drafts),
            "quality_gate_pass_rate": round((pass_count / len(drafts)) * 100, 1),
            "average_text_overlap_percent": round(sum(overlap_values) / len(overlap_values), 1) if overlap_values else 0,
            "average_rewrite_count": round(rewrite_count / project_count, 2),
            "high_risk_rate": round((high_risk_count / len(drafts)) * 100, 1),
            "failed_gate_reasons": self._failed_gate_reasons(failed_reasons, len(drafts)),
        }

    def _add_failed_gate_reasons(self, reasons: dict[str, dict[str, Any]], quality_gate: dict[str, Any]) -> None:
        checks = quality_gate.get("checks") if isinstance(quality_gate.get("checks"), list) else []
        failed_checks = {str(item) for item in quality_gate.get("failed_checks") or []}
        if checks:
            for check in checks:
                if not isinstance(check, dict) or check.get("passed") is True:
                    continue
                key = str(check.get("key") or "")
                if not key:
                    continue
                label = str(check.get("label") or key)
                self._increment_failed_gate_reason(reasons, key, label)
            return
        for key in failed_checks:
            if key:
                self._increment_failed_gate_reason(reasons, key, self._quality_gate_reason_label(key))

    def _increment_failed_gate_reason(self, reasons: dict[str, dict[str, Any]], key: str, label: str) -> None:
        item = reasons.setdefault(key, {"key": key, "label": label, "count": 0})
        item["count"] = self._as_int(item.get("count")) + 1
        if label and item.get("label") == key:
            item["label"] = label

    def _failed_gate_reasons(self, reasons: dict[str, dict[str, Any]], draft_count: int) -> list[dict[str, Any]]:
        if draft_count <= 0:
            return []
        ranked = sorted(reasons.values(), key=lambda item: (-self._as_int(item.get("count")), str(item.get("key") or "")))
        return [
            {
                "key": str(item.get("key") or ""),
                "label": str(item.get("label") or item.get("key") or ""),
                "count": self._as_int(item.get("count")),
                "draft_percent": round((self._as_int(item.get("count")) / draft_count) * 100, 1),
                "next_action": self._quality_gate_reason_action(str(item.get("key") or "")),
            }
            for item in ranked[:6]
        ]

    def _quality_gate_reason_label(self, key: str) -> str:
        return {
            "text_overlap": "文本重合",
            "repeated_phrases": "重复短语",
            "reused_entities": "复用设定",
            "structure_similarity": "结构接近",
            "style_similarity": "风格接近",
            "semantic_similarity": "语义桥段",
        }.get(key, key)

    def _quality_gate_reason_action(self, key: str) -> str:
        return {
            "text_overlap": "先做降风险改写，降低连续表达和句式重合。",
            "repeated_phrases": "替换重复短语，并改写承接句。",
            "reused_entities": "更换人物、身份、地点和关键设定。",
            "structure_similarity": "调整事件顺序和反转兑现方式。",
            "style_similarity": "切换叙述口吻、句长和节奏。",
            "semantic_similarity": "重构事件载体、动机和公开反转场景。",
        }.get(key, "查看质检报告并优先处理未通过项。")

    def _creation_funnel(
        self,
        *,
        recent_videos: list[dict[str, Any]],
        reports: list[dict[str, Any]],
        projects: list[dict[str, Any]],
    ) -> dict[str, Any]:
        draft_count = 0
        publishable_count = 0
        for project in projects:
            drafts = project.get("generated_drafts") if isinstance(project.get("generated_drafts"), list) else []
            draft_count += len(drafts)
            publishable_count += sum(1 for draft in drafts if isinstance(draft, dict) and str(draft.get("status") or "") == "publishable")

        steps = [
            {"key": "synced_videos", "label": "Synced videos", "count": len(recent_videos)},
            {"key": "analyzed_reports", "label": "Analyzed reports", "count": len(reports)},
            {"key": "creation_projects", "label": "Creation projects", "count": len(projects)},
            {"key": "generated_drafts", "label": "Generated drafts", "count": draft_count},
            {"key": "publishable_drafts", "label": "Publishable drafts", "count": publishable_count},
        ]
        previous = 0
        for index, step in enumerate(steps):
            count = self._as_int(step.get("count"))
            if index == 0:
                step["conversion_percent"] = 100.0 if count else 0.0
            else:
                step["conversion_percent"] = round((count / previous) * 100, 1) if previous else 0.0
            previous = count

        bottlenecks = [
            {
                "from": steps[index - 1]["key"],
                "to": steps[index]["key"],
                "conversion_percent": steps[index]["conversion_percent"],
            }
            for index in range(1, len(steps))
        ]
        bottleneck = min(bottlenecks, key=lambda item: item["conversion_percent"]) if bottlenecks else None
        if bottleneck:
            bottleneck.update(self._creation_funnel_bottleneck_advice(str(bottleneck.get("from") or ""), str(bottleneck.get("to") or "")))
        return {"steps": steps, "bottleneck": bottleneck}

    def _creation_funnel_bottleneck_advice(self, source: str, target: str) -> dict[str, str]:
        advice = {
            ("synced_videos", "analyzed_reports"): {
                "summary": "候选视频进入分析报告的比例最低。",
                "next_action": "优先从候选池选择高分视频批量分析，补齐报告和字幕证据。",
            },
            ("analyzed_reports", "creation_projects"): {
                "summary": "报告没有及时转成创作项目。",
                "next_action": "进入创作转化工坊，为已分析报告生成 InkOS 创作包。",
            },
            ("creation_projects", "generated_drafts"): {
                "summary": "创作包没有及时产出草稿。",
                "next_action": "运行 InkOS，或粘贴人工草稿并保存质检。",
            },
            ("generated_drafts", "publishable_drafts"): {
                "summary": "草稿到可发布的通过率最低。",
                "next_action": "优先处理质检失败项，使用降风险改写或桥段重构生成新版本。",
            },
        }
        return advice.get(
            (source, target),
            {
                "summary": "当前漏斗存在转化偏低的环节。",
                "next_action": "查看对应工作台，补齐缺失步骤后再刷新看板。",
            },
        )

    def _weekly_production_metrics(
        self,
        *,
        reports: list[dict[str, Any]],
        projects: list[dict[str, Any]],
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        window_start = now - timedelta(days=7)
        recent_reports = [report for report in reports if self._is_recent_workspace_item(report, window_start)]
        recent_projects = [project for project in projects if self._is_recent_workspace_item(project, window_start)]
        recent_drafts: list[dict[str, Any]] = []
        for project in projects:
            drafts = project.get("generated_drafts") if isinstance(project.get("generated_drafts"), list) else []
            recent_drafts.extend(
                draft
                for draft in drafts
                if isinstance(draft, dict) and self._is_recent_workspace_item(draft, window_start)
            )

        publishable_drafts = [
            draft
            for draft in recent_drafts
            if str(draft.get("status") or "") == "publishable"
        ]
        return {
            "window_days": 7,
            "window_start": window_start.isoformat(),
            "window_end": now.isoformat(),
            "analyzed_report_count": len(recent_reports),
            "created_project_count": len(recent_projects),
            "generated_draft_count": len(recent_drafts),
            "publishable_draft_count": len(publishable_drafts),
        }

    def _is_recent_workspace_item(self, item: dict[str, Any], window_start: datetime) -> bool:
        timestamp = self._parse_workspace_timestamp(item.get("updated_at") or item.get("created_at"))
        return bool(timestamp and timestamp >= window_start)

    def _parse_workspace_timestamp(self, value: Any) -> datetime | None:
        if not value:
            return None
        try:
            timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(UTC)

    def save_favorite_structure_template(self, project_id: str) -> dict[str, Any]:
        holder: dict[str, Any] = {}

        def save(data: dict[str, Any]) -> None:
            project = self._find_by_id(data["imitation_projects"], project_id)
            if not project:
                raise ValueError("Imitation project not found.")
            templates = data.setdefault("favorite_structure_templates", [])
            existing = self._find_by_id(templates, project_id, key="source_project_id")
            template = self._structure_template_from_project(project)
            if existing:
                existing.update(template)
                holder["template"] = existing
            else:
                templates.insert(0, template)
                holder["template"] = template

        self.update(save)
        return {"template": holder["template"]}

    def delete_favorite_structure_template(self, project_id: str) -> dict[str, Any]:
        holder: dict[str, Any] = {}

        def delete(data: dict[str, Any]) -> None:
            templates = data.setdefault("favorite_structure_templates", [])
            before = len(templates)
            data["favorite_structure_templates"] = [
                item for item in templates if str(item.get("source_project_id") or "") != project_id
            ]
            holder["removed"] = before - len(data["favorite_structure_templates"])

        self.update(delete)
        return {"removed": holder["removed"]}

    def update_favorite_structure_template(self, template_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        allowed = {"name", "tags", "notes", "applicable_topics", "success_cases"}
        cleaned_patch = {key: value for key, value in patch.items() if key in allowed}
        holder: dict[str, Any] = {}

        def update(data: dict[str, Any]) -> None:
            template = self._find_by_id(data.setdefault("favorite_structure_templates", []), template_id)
            if not template:
                raise ValueError("Structure template not found.")
            if "name" in cleaned_patch:
                name = str(cleaned_patch.get("name") or "").strip()
                if name:
                    template["name"] = name
            if "notes" in cleaned_patch:
                template["notes"] = str(cleaned_patch.get("notes") or "").strip()
            for key in ("tags", "applicable_topics", "success_cases"):
                if key in cleaned_patch:
                    template[key] = self._clean_string_list(cleaned_patch.get(key))
            template["updated_at"] = utc_now_iso()
            holder["template"] = template

        self.update(update)
        return {"template": holder["template"]}

    def _imitation_project_summaries(
        self,
        projects: list[dict[str, Any]],
        favorite_templates: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        favorite_project_ids = {
            str(template.get("source_project_id") or "")
            for template in (favorite_templates or [])
            if isinstance(template, dict)
        }
        summaries: list[dict[str, Any]] = []
        for project in projects:
            drafts = project.get("generated_drafts", [])
            latest_draft = drafts[0] if drafts else {}
            draft_report = latest_draft.get("similarity_report") if isinstance(latest_draft.get("similarity_report"), dict) else {}
            latest_report = project.get("latest_similarity_report") if isinstance(project.get("latest_similarity_report"), dict) else {}
            if not latest_report:
                latest_report = draft_report
            quality_gate = latest_report.get("quality_gate") if isinstance(latest_report.get("quality_gate"), dict) else {}
            if not quality_gate:
                quality_gate = draft_report.get("quality_gate") if isinstance(draft_report.get("quality_gate"), dict) else {}
            latest_draft_status = str(latest_draft.get("status") or "")
            latest_risk_level = str(latest_report.get("risk_level") or project.get("risk_level") or "")
            latest_quality_gate_status = str(quality_gate.get("status") or "")
            production_stage = self._project_production_stage(
                draft_count=len(drafts),
                latest_draft_status=latest_draft_status,
                latest_risk_level=latest_risk_level,
                latest_quality_gate_status=latest_quality_gate_status,
            )
            priority = self._project_production_priority(
                production_stage=production_stage,
                latest_risk_level=latest_risk_level,
                latest_quality_gate_status=latest_quality_gate_status,
                latest_draft_status=latest_draft_status,
            )
            summaries.append(
                {
                    "id": str(project.get("id") or ""),
                    "name": str(project.get("name") or ""),
                    "source_video_title": str(project.get("source_video_title") or ""),
                    "source_video_url": str(project.get("source_video_url") or ""),
                    "source_channel_title": str(project.get("source_channel_title") or ""),
                    "source_topic_type": str(project.get("source_topic_type") or ""),
                    "direction": str(project.get("direction") or ""),
                    "output_type": str(project.get("output_type") or ""),
                    "similarity_level": str(project.get("similarity_level") or ""),
                    "inkos_status": str(project.get("inkos_status") or ""),
                    "draft_count": len(drafts),
                    "latest_draft_status": latest_draft_status,
                    "latest_risk_level": latest_risk_level,
                    "latest_quality_gate_status": latest_quality_gate_status,
                    "latest_quality_gate_summary": str(quality_gate.get("summary") or ""),
                    "text_overlap_percent": latest_report.get("text_overlap_percent", 0),
                    "production_stage": production_stage,
                    "production_priority": priority["priority"],
                    "production_priority_reason": priority["reason"],
                    "recommended_next_action": priority["next_action"],
                    "template_favorited": str(project.get("id") or "") in favorite_project_ids,
                    "updated_at": str(latest_draft.get("updated_at") or latest_draft.get("created_at") or project.get("created_at") or ""),
                    "created_at": str(project.get("created_at") or ""),
                }
            )
        return summaries

    def _project_production_stage(
        self,
        *,
        draft_count: int,
        latest_draft_status: str,
        latest_risk_level: str,
        latest_quality_gate_status: str,
    ) -> str:
        if draft_count <= 0:
            return "reference"
        if latest_draft_status == "discarded":
            return "discarded"
        if latest_draft_status == "publishable" and latest_quality_gate_status != "blocked":
            return "publishable"
        if (
            latest_draft_status == "needs_revision"
            or latest_risk_level == "high"
            or latest_quality_gate_status == "blocked"
        ):
            return "needs_revision"
        return "needs_review"

    def _project_production_priority(
        self,
        *,
        production_stage: str,
        latest_risk_level: str,
        latest_quality_gate_status: str,
        latest_draft_status: str,
    ) -> dict[str, str]:
        if latest_quality_gate_status == "blocked":
            return {
                "priority": "urgent",
                "reason": "质量门禁阻断，不能标记可发布。",
                "next_action": "先运行风险段落改写或桥段重构，再重新检测。",
            }
        if latest_risk_level == "high":
            return {
                "priority": "urgent",
                "reason": "最新稿件仍是高风险。",
                "next_action": "优先降低文本重合、设定复用或语义桥段相似度。",
            }
        if production_stage == "needs_revision" or latest_draft_status == "needs_revision":
            return {
                "priority": "high",
                "reason": "稿件需要修改后才能进入终审。",
                "next_action": "打开创作工坊，根据质检失败项生成改写版本。",
            }
        if production_stage == "needs_review" or latest_draft_status == "needs_review":
            return {
                "priority": "medium",
                "reason": "稿件等待人工审查或补充质检。",
                "next_action": "检查质量门禁和风险段落，确认是否可发布。",
            }
        if production_stage == "reference":
            return {
                "priority": "medium",
                "reason": "已有参考包但还没有草稿。",
                "next_action": "运行 InkOS 或粘贴草稿并完成风险检测。",
            }
        if production_stage == "publishable":
            return {
                "priority": "low",
                "reason": "已有可发布稿件。",
                "next_action": "导出文案，或收藏结构模板用于后续复用。",
            }
        return {
            "priority": "low",
            "reason": "项目暂不需要立即处理。",
            "next_action": "保留归档，必要时重新打开检查。",
        }

    def _structure_template_from_project(self, project: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": f"template-{project.get('id') or unique_workspace_id('template')}",
            "source_project_id": str(project.get("id") or ""),
            "name": str(project.get("name") or "Structure template"),
            "source_video_title": str(project.get("source_video_title") or ""),
            "source_channel_title": str(project.get("source_channel_title") or ""),
            "source_topic_type": str(project.get("source_topic_type") or ""),
            "output_type": str(project.get("output_type") or ""),
            "structure_template": [
                str(item) for item in project.get("structure_template", []) if str(item).strip()
            ],
            "reuse_constraints": [
                str(item) for item in project.get("reuse_constraints", []) if str(item).strip()
            ],
            "anti_copy_rules": [
                str(item) for item in project.get("anti_copy_rules", []) if str(item).strip()
            ],
            "tags": [str(project.get("source_topic_type") or ""), str(project.get("output_type") or "")],
            "notes": "",
            "applicable_topics": [str(project.get("source_topic_type") or "")] if str(project.get("source_topic_type") or "") else [],
            "success_cases": [],
            "reuse_count": 0,
            "publishable_rate": 0,
            "average_risk_level": "",
            "average_text_overlap_percent": 0,
            "created_at": utc_now_iso(),
        }

    def _favorite_structure_templates_with_metrics(
        self,
        templates: list[dict[str, Any]],
        projects: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            {
                **template,
                **self._structure_template_metrics(template, projects),
            }
            for template in templates
            if isinstance(template, dict)
        ]

    def _structure_template_metrics(self, template: dict[str, Any], projects: list[dict[str, Any]]) -> dict[str, Any]:
        template_id = str(template.get("id") or "")
        source_project_id = str(template.get("source_project_id") or "")
        reused_projects = [
            project
            for project in projects
            if str(project.get("source_template_id") or "") == template_id
            or (source_project_id and str(project.get("source_template_id") or "") == source_project_id)
        ]
        risk_scores: list[int] = []
        overlaps: list[float] = []
        publishable_count = 0
        for project in reused_projects:
            drafts = project.get("generated_drafts") if isinstance(project.get("generated_drafts"), list) else []
            latest_draft = drafts[0] if drafts else {}
            latest_report = project.get("latest_similarity_report") if isinstance(project.get("latest_similarity_report"), dict) else {}
            draft_report = latest_draft.get("similarity_report") if isinstance(latest_draft.get("similarity_report"), dict) else {}
            report = latest_report or draft_report
            risk = str(report.get("risk_level") or "")
            if risk in {"low", "medium", "high"}:
                risk_scores.append({"low": 1, "medium": 2, "high": 3}[risk])
            try:
                overlaps.append(float(report.get("text_overlap_percent") or 0))
            except (TypeError, ValueError):
                overlaps.append(0)
            if str(latest_draft.get("status") or "") == "publishable":
                publishable_count += 1
        reuse_count = len(reused_projects)
        average_risk_score = round(sum(risk_scores) / len(risk_scores), 2) if risk_scores else 0
        average_risk_level = self._risk_label_from_score(average_risk_score)
        return {
            "reuse_count": reuse_count,
            "publishable_rate": round((publishable_count / reuse_count) * 100, 1) if reuse_count else 0,
            "average_risk_level": average_risk_level,
            "average_text_overlap_percent": round(sum(overlaps) / len(overlaps), 1) if overlaps else 0,
            "recommendation_summary": self._structure_template_recommendation_summary(
                reuse_count=reuse_count,
                publishable_count=publishable_count,
                average_risk_level=average_risk_level,
                average_overlap=round(sum(overlaps) / len(overlaps), 1) if overlaps else 0,
            ),
            "recommended_usage": self._structure_template_recommended_usage(template, reuse_count, publishable_count),
        }

    def _structure_template_recommendation_summary(
        self,
        *,
        reuse_count: int,
        publishable_count: int,
        average_risk_level: str,
        average_overlap: float,
    ) -> str:
        if reuse_count <= 0:
            return "尚未复用，适合先在小批量项目中试跑。"
        publishable_rate = round((publishable_count / reuse_count) * 100, 1) if reuse_count else 0
        if publishable_rate >= 60 and average_risk_level in {"", "low", "medium"}:
            return f"已复用 {reuse_count} 次，通过率 {publishable_rate}%，可作为优先模板。"
        if average_risk_level == "high" or average_overlap >= 18:
            return f"已复用 {reuse_count} 次，但平均风险偏高，复用前应降低参考强度。"
        return f"已复用 {reuse_count} 次，通过率 {publishable_rate}%，建议继续观察质量表现。"

    def _structure_template_recommended_usage(self, template: dict[str, Any], reuse_count: int, publishable_count: int) -> str:
        topics = [str(item) for item in template.get("applicable_topics") or [] if str(item).strip()]
        topic_text = "、".join(topics[:3]) if topics else str(template.get("source_topic_type") or "相近题材")
        if reuse_count and publishable_count / max(reuse_count, 1) >= 0.6:
            return f"适合用于{topic_text}的公开反转、身份差或爽点兑现类故事。"
        return f"适合先用于{topic_text}的小批量草稿，生成后重点检查设定复用和桥段相似度。"

    def _risk_label_from_score(self, score: float) -> str:
        if score >= 2.5:
            return "high"
        if score >= 1.5:
            return "medium"
        if score > 0:
            return "low"
        return ""

    def _clean_string_list(self, value: Any) -> list[str]:
        if isinstance(value, str):
            values = re.split(r"[,，\n]+", value)
        elif isinstance(value, list):
            values = value
        else:
            return []
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in values:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            cleaned.append(text)
            seen.add(text)
        return cleaned

    def _dedupe_videos(self, videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for video in videos:
            key = str(video.get("url") or video.get("youtube_video_id") or video.get("id") or "")
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            deduped.append(video)
        return deduped

    def _find_by_id(self, items: list[dict[str, Any]], item_id: str, *, key: str = "id") -> dict[str, Any] | None:
        for item in items:
            if isinstance(item, dict) and str(item.get(key) or "") == item_id:
                return item
        return None

    def _collection_evidence(self, tool_results: dict[str, dict]) -> dict[str, Any]:
        metadata = tool_results.get("get_video_metadata", {})
        transcript = tool_results.get("get_transcript", {})
        comments = tool_results.get("get_comments", {})
        llm_analysis = tool_results.get("analyze_with_llm", {})
        transcript_source = str(transcript.get("source") or "")
        transcript_text = str(transcript.get("text") or "")
        analysis_source = str(llm_analysis.get("source") or "")
        analysis_status = str(llm_analysis.get("status") or "")
        return {
            "metadata_source": metadata.get("collection_source") or "",
            "metadata_status": metadata.get("collection_status") or "",
            "transcript_source": transcript_source,
            "transcript_language": transcript.get("language") or "",
            "transcript_status": "ok" if transcript_text else "missing",
            "transcript_length": len(transcript_text),
            "is_auto_caption": self._is_auto_caption(transcript_source),
            "transcript_error": transcript.get("error_message") or "",
            "comments_status": comments.get("status") or "",
            "analysis_source": analysis_source,
            "analysis_status": analysis_status,
            "analysis_error": llm_analysis.get("error_message") or "",
            "llm_participated": analysis_source == "llm" and analysis_status == "ok",
            "used_rule_fallback": analysis_source == "rule_fallback" or analysis_status == "failed",
        }

    def _enrich_report(self, report: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        enriched = {**report}
        evidence = {
            **(report.get("collection_evidence") if isinstance(report.get("collection_evidence"), dict) else {})
        }
        video_id = str(report.get("youtube_video_id") or "")
        transcript_record = TranscriptStore(self.settings).get_transcript(video_id) if video_id else None
        transcript_source = str(transcript_record.get("transcript_source") if transcript_record else evidence.get("transcript_source") or "")
        transcript_length = (
            int(transcript_record.get("raw_length") or 0)
            if transcript_record
            else self._as_int(evidence.get("transcript_length"))
        )
        transcript_language = str(transcript_record.get("language") if transcript_record else evidence.get("transcript_language") or "")
        analysis_source = str(evidence.get("analysis_source") or "")
        analysis_status = str(evidence.get("analysis_status") or "")
        sample = self._sample_for_report(report, data)
        frame_count = self._as_int(sample.get("frame_count")) if sample else self._as_int(evidence.get("frame_count"))

        evidence.update(
            {
                "transcript_source": transcript_source,
                "transcript_language": transcript_language,
                "transcript_status": "ok" if transcript_length > 0 else evidence.get("transcript_status") or "missing",
                "transcript_length": transcript_length,
                "is_auto_caption": self._is_auto_caption(transcript_source),
                "llm_participated": analysis_source == "llm" and analysis_status == "ok",
                "used_rule_fallback": analysis_source == "rule_fallback" or analysis_status == "failed",
                "frame_status": "ok" if frame_count > 0 else "missing",
                "frame_count": frame_count,
            }
        )
        enriched["collection_evidence"] = evidence
        return enriched

    def _sample_for_report(self, report: dict[str, Any], data: dict[str, Any]) -> dict[str, Any] | None:
        video_url = str(report.get("video_url") or "")
        video_id = str(report.get("youtube_video_id") or "")
        for sample in data["sample_analyses"]:
            if not isinstance(sample, dict):
                continue
            if video_url and str(sample.get("video_url") or "") == video_url:
                return sample
            if video_id and str(sample.get("video_id") or "") == video_id:
                return sample
        return None

    def _is_auto_caption(self, source: str) -> bool:
        normalized = source.lower()
        return "auto" in normalized or "automatic" in normalized

    def _as_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
