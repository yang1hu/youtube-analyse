from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from creator_agent.config import Settings
from creator_agent.services.workspace_store import WorkspaceStore, unique_workspace_id


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class ScriptStudioService:
    def __init__(self, settings: Settings | None = None, store: WorkspaceStore | None = None) -> None:
        self.settings = settings or Settings()
        self.store = store or WorkspaceStore(self.settings)

    def list_scripts(self) -> dict[str, Any]:
        return {"script_drafts": self.store.load()["script_drafts"]}

    def generate_script(self, idea_id: str, style_id: str | None = None) -> dict[str, Any]:
        holder: dict[str, Any] = {}

        def generate(data: dict[str, Any]) -> None:
            idea = self._find_idea(data, idea_id)
            if not idea:
                raise ValueError("Idea card not found.")
            style = self._find_by_id(data["style_profiles"], style_id or "") or {}
            script = self._build_script(
                idea=idea,
                style=style,
                parent_id="",
                version=1,
            )
            data["script_drafts"].insert(0, script)
            holder["script"] = script

        self.store.update(generate)
        return {"script_draft": holder["script"]}

    def rewrite_script(self, script_id: str, style_id: str | None = None) -> dict[str, Any]:
        holder: dict[str, Any] = {}

        def rewrite(data: dict[str, Any]) -> None:
            original = self._find_by_id(data["script_drafts"], script_id)
            if not original:
                raise ValueError("Script draft not found.")
            idea = self._find_idea(data, str(original.get("idea_id") or ""))
            if not idea:
                idea = {
                    "id": original.get("idea_id") or "idea",
                    "title": original.get("selected_title") or "Untitled script",
                    "angle": original.get("angle") or "",
                    "why_it_works": "",
                    "outline": [],
                    "risk_notes": "",
                }
            style = self._find_by_id(data["style_profiles"], style_id or str(original.get("style_id") or "")) or {}
            version = self._next_version(data["script_drafts"], script_id)
            script = self._build_script(
                idea=idea,
                style=style,
                parent_id=script_id,
                version=version,
            )
            data["script_drafts"].insert(0, script)
            holder["script"] = script

        self.store.update(rewrite)
        return {"script_draft": holder["script"]}

    def update_script(
        self,
        script_id: str,
        *,
        selected_title: str | None = None,
        opening_30s: str | None = None,
        full_script: str | None = None,
    ) -> dict[str, Any]:
        holder: dict[str, Any] = {}

        def update(data: dict[str, Any]) -> None:
            original = self._find_by_id(data["script_drafts"], script_id)
            if not original:
                raise ValueError("Script draft not found.")

            idea = self._find_idea(data, str(original.get("idea_id") or "")) or {}
            style = self._find_by_id(data["style_profiles"], str(original.get("style_id") or "")) or {}
            title_options = list(original.get("title_options") if isinstance(original.get("title_options"), list) else [])
            next_title = (selected_title or str(original.get("selected_title") or "")).strip()
            if next_title and next_title not in title_options:
                title_options.insert(0, next_title)
            if not title_options:
                title_options = self._title_options(idea, style)
                next_title = next_title or title_options[0]

            script = {
                **original,
                "id": self._next_script_id(data["script_drafts"]),
                "parent_id": script_id,
                "version": self._next_version(data["script_drafts"], script_id),
                "title_options": title_options,
                "selected_title": next_title or title_options[0],
                "opening_30s": (opening_30s or str(original.get("opening_30s") or "")).strip(),
                "full_script": (full_script or str(original.get("full_script") or "")).strip(),
                "created_at": utc_now_iso(),
            }
            if not script["opening_30s"]:
                script["opening_30s"] = self._opening_30s(idea, style, int(script["version"]))
            if not script["full_script"]:
                script["full_script"] = self._full_script(idea, style, script["opening_30s"])
            script["markdown"] = self._markdown(script, idea, style)
            data["script_drafts"].insert(0, script)
            holder["script"] = script

        self.store.update(update)
        return {"script_draft": holder["script"]}

    def export_markdown(self, script_id: str) -> dict[str, str]:
        script = self._find_by_id(self.store.load()["script_drafts"], script_id)
        if not script:
            raise ValueError("Script draft not found.")
        title = self._slug(str(script.get("selected_title") or script_id))
        return {"filename": f"{title}.md", "markdown": str(script.get("markdown") or "")}

    def _build_script(
        self,
        idea: dict[str, Any],
        style: dict[str, Any],
        parent_id: str,
        version: int,
    ) -> dict[str, Any]:
        title_options = self._title_options(idea, style)
        selected_title = title_options[0]
        opening_30s = self._opening_30s(idea, style, version)
        full_script = self._full_script(idea, style, opening_30s)
        script = {
            "id": unique_workspace_id("script"),
            "idea_id": idea.get("id") or "",
            "style_id": style.get("id") or "",
            "parent_id": parent_id,
            "version": version,
            "title_options": title_options,
            "selected_title": selected_title,
            "opening_30s": opening_30s,
            "full_script": full_script,
            "created_at": utc_now_iso(),
        }
        script["markdown"] = self._markdown(script, idea, style)
        return script

    def _title_options(self, idea: dict[str, Any], style: dict[str, Any]) -> list[str]:
        title = str(idea.get("title") or "New video idea")
        angle = str(idea.get("angle") or "status reversal")
        formula = str(style.get("title_formula") or "Hidden rule creates a visible payoff")
        return [
            title,
            f"{angle}: {formula}",
            f"No one noticed the tiny trigger until the reward changed everything",
        ]

    def _opening_30s(self, idea: dict[str, Any], style: dict[str, Any], version: int) -> str:
        opening_formula = str(style.get("opening_formula") or "Open with the consequence before the explanation.")
        angle = str(idea.get("angle") or "")
        why = str(idea.get("why_it_works") or "")
        suffix = f" Version {version}." if version > 1 else ""
        return (
            f"Start on the visible consequence: {angle}. "
            f"Do not explain the system yet. Show the public misunderstanding, then let the tiny action trigger the first payoff. "
            f"Style rule: {opening_formula}. Retention reason: {why}.{suffix}"
        )

    def _full_script(self, idea: dict[str, Any], style: dict[str, Any], opening_30s: str) -> str:
        outline = idea.get("outline") if isinstance(idea.get("outline"), list) else []
        rules = style.get("reusable_rules") if isinstance(style.get("reusable_rules"), list) else []
        sections = [f"Opening 30s: {opening_30s}"]
        for index, item in enumerate(outline[:8], start=1):
            sections.append(f"Beat {index}: {item}")
        if not outline:
            sections.extend(
                [
                    "Beat 1: Establish the public pressure.",
                    "Beat 2: Trigger the hidden rule with a small action.",
                    "Beat 3: Let bystanders misread the situation.",
                    "Beat 4: Reveal a bigger reward and force a status reversal.",
                    "Beat 5: End with a larger unresolved trigger.",
                ]
            )
        if rules:
            sections.append("Reusable style rules: " + " / ".join(rules[:4]))
        sections.append("Avoid copying: " + str(idea.get("risk_notes") or "Change names, scenes, and plot specifics."))
        return "\n".join(sections)

    def _markdown(self, script: dict[str, Any], idea: dict[str, Any], style: dict[str, Any]) -> str:
        titles = "\n".join(f"{index}. {title}" for index, title in enumerate(script["title_options"], start=1))
        return "\n\n".join(
            [
                f"# {script['selected_title']}",
                f"Version {script['version']}",
                f"Style: {style.get('name') or 'No style selected'}",
                "## Title Options\n" + titles,
                "## Opening 30 Seconds\n" + script["opening_30s"],
                "## Full Script\n" + script["full_script"],
                "## Risk Notes\n" + str(idea.get("risk_notes") or "Avoid copying the source directly."),
            ]
        )

    def _find_idea(self, data: dict[str, Any], idea_id: str) -> dict[str, Any] | None:
        ideas = list(data["idea_cards"])
        for report in data["reports"]:
            report_ideas = report.get("idea_cards") if isinstance(report.get("idea_cards"), list) else []
            for index, idea in enumerate(report_ideas):
                if isinstance(idea, dict):
                    ideas.append({"id": idea.get("id") or f"{report.get('id', 'report')}-idea-{index + 1}", **idea})
        return self._find_by_id(ideas, idea_id)

    def _find_by_id(self, items: list[dict[str, Any]], item_id: str) -> dict[str, Any] | None:
        for item in items:
            if str(item.get("id") or "") == item_id:
                return item
        return None

    def _next_script_id(self, scripts: list[dict[str, Any]]) -> str:
        existing = {str(script.get("id") or "") for script in scripts}
        script_id = unique_workspace_id("script")
        while script_id in existing:
            script_id = unique_workspace_id("script")
        return script_id

    def _next_version(self, scripts: list[dict[str, Any]], parent_id: str) -> int:
        versions = [
            int(script.get("version") or 1)
            for script in scripts
            if script.get("id") == parent_id or script.get("parent_id") == parent_id
        ]
        return max(versions or [1]) + 1

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value).strip("-").lower()
        return slug[:80] or "script-draft"
