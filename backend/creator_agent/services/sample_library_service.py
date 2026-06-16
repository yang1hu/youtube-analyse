from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from creator_agent.config import Settings
from creator_agent.services.workspace_store import WorkspaceStore, unique_workspace_id


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class SampleLibraryService:
    def __init__(self, settings: Settings | None = None, store: WorkspaceStore | None = None) -> None:
        self.settings = settings or Settings()
        self.store = store or WorkspaceStore(self.settings)

    def list_samples(self) -> dict[str, Any]:
        samples = [self._normalize_sample(sample) for sample in self.store.load()["sample_analyses"]]
        return {
            "samples": sorted(samples, key=lambda sample: (not sample.get("favorite", False), sample.get("created_at", ""))),
            "tag_suggestions": self._tag_suggestions(samples),
        }

    def update_sample(self, sample_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        holder: dict[str, Any] = {}

        def update(data: dict[str, Any]) -> None:
            for index, sample in enumerate(data["sample_analyses"]):
                if str(sample.get("id") or "") != sample_id:
                    continue
                updated = self._normalize_sample(
                    {
                        **sample,
                        "favorite": bool(patch.get("favorite", sample.get("favorite", False))),
                        "tags": self._clean_tags(patch.get("tags", sample.get("tags", []))),
                        "notes": str(patch.get("notes", sample.get("notes", ""))).strip(),
                        "updated_at": utc_now_iso(),
                    }
                )
                data["sample_analyses"][index] = updated
                holder["sample"] = updated
                return
            raise ValueError("Sample not found.")

        self.store.update(update)
        return {"sample": holder["sample"]}

    def merge_style(self, sample_ids: list[str], name: str) -> dict[str, Any]:
        if len(sample_ids) < 2:
            raise ValueError("Select at least two samples to merge.")

        holder: dict[str, Any] = {}

        def merge(data: dict[str, Any]) -> None:
            samples = [self._normalize_sample(sample) for sample in data["sample_analyses"] if str(sample.get("id") or "") in sample_ids]
            if len(samples) != len(set(sample_ids)):
                raise ValueError("One or more samples were not found.")

            style = {
                "id": unique_workspace_id("sample-style"),
                "name": name.strip() or "Merged sample style",
                "source_sample_ids": sample_ids,
                "source_video_title": " + ".join(sample["video_title"] for sample in samples[:3]),
                "topic_type": "sample_library_merge",
                "opening_formula": " / ".join(self._unique(sample.get("opening_hook", "") for sample in samples)[:3]),
                "rhythm_formula": self._unique(note for sample in samples for note in sample.get("pacing_notes", [])),
                "hook_patterns": self._unique(sample.get("opening_hook", "") for sample in samples),
                "reusable_rules": self._unique(rule for sample in samples for rule in sample.get("reuse_template", [])),
                "avoid_copying": self._unique(note for sample in samples for note in sample.get("risk_notes", [])),
                "created_at": utc_now_iso(),
            }
            data["style_profiles"].insert(0, style)
            holder["style"] = style

        self.store.update(merge)
        return {"style_profile": holder["style"]}

    def _normalize_sample(self, sample: dict[str, Any]) -> dict[str, Any]:
        return {
            **sample,
            "favorite": bool(sample.get("favorite", False)),
            "tags": self._clean_tags(sample.get("tags", [])),
            "notes": str(sample.get("notes") or ""),
            "pacing_notes": sample.get("pacing_notes") if isinstance(sample.get("pacing_notes"), list) else [],
            "reuse_template": sample.get("reuse_template") if isinstance(sample.get("reuse_template"), list) else [],
            "risk_notes": sample.get("risk_notes") if isinstance(sample.get("risk_notes"), list) else [],
        }

    def _clean_tags(self, tags: Any) -> list[str]:
        if not isinstance(tags, list):
            return []
        cleaned: list[str] = []
        for tag in tags:
            normalized = str(tag).strip()
            if normalized and normalized not in cleaned:
                cleaned.append(normalized)
        return cleaned

    def _tag_suggestions(self, samples: list[dict[str, Any]]) -> list[str]:
        defaults = ["story_recap", "system", "ai_tools", "knowledge", "viral_opening"]
        existing = self._unique(tag for sample in samples for tag in sample.get("tags", []))
        return self._unique([*existing, *defaults])

    def _unique(self, values) -> list[str]:
        items: list[str] = []
        for value in values:
            normalized = str(value).strip()
            if normalized and normalized not in items:
                items.append(normalized)
        return items
