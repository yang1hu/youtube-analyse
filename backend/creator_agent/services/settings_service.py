import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

from creator_agent.config import Settings


class WorkspaceSettings(BaseModel):
    channel_url: str = ""
    channel_urls: list[str] = Field(default_factory=list)
    browser_engine: Literal["playwright", "drission", "cdp"] = "playwright"
    browser_headless: bool = True
    browser_path: str = ""
    browser_debug_port: int | None = Field(default=None, ge=1, le=65535)
    browser_cdp_url: str = "http://127.0.0.1:9222"
    openai_base_url: str = "http://localhost:53881/v1"
    openai_translation_model: str = "gpt-5.5"
    openai_analysis_model: str = "gpt-5.5"
    openai_api_key: str = ""
    openai_api_key_set: bool = False
    monitor_enabled: bool = False
    monitor_interval_minutes: int = Field(default=180, ge=30, le=10080)
    monitor_auto_analyze: bool = False
    monitor_auto_translate: bool = False
    monitor_min_views: int = Field(default=0, ge=0)

    @field_validator("channel_url")
    @classmethod
    def validate_channel_url(cls, value: str) -> str:
        return cls._validate_channel_url(value)

    @field_validator("channel_urls")
    @classmethod
    def validate_channel_urls(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            channel_url = cls._validate_channel_url(str(item))
            if channel_url and channel_url not in seen:
                normalized.append(channel_url)
                seen.add(channel_url)
        return normalized

    @model_validator(mode="after")
    def sync_legacy_channel_url(self) -> "WorkspaceSettings":
        urls = list(self.channel_urls)
        if self.channel_url and self.channel_url not in urls:
            urls.insert(0, self.channel_url)
        if urls:
            self.channel_urls = urls
            self.channel_url = urls[0]
        else:
            self.channel_url = ""
        return self

    @classmethod
    def _validate_channel_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized:
            return ""

        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Channel URL must start with http:// or https://.")
        if parsed.netloc.lower() not in {"youtube.com", "www.youtube.com"}:
            raise ValueError("Channel URL must be a YouTube URL.")
        if not (
            parsed.path.startswith("/@")
            or parsed.path.startswith("/channel/")
            or parsed.path.startswith("/c/")
            or parsed.path.startswith("/user/")
        ):
            raise ValueError("Channel URL must point to a YouTube channel.")
        return normalized


class WorkspaceSettingsService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.path = Path(self.settings.workspace_settings_path)

    def get(self) -> WorkspaceSettings:
        defaults = self._default_settings()
        if not self.path.exists():
            return self._public_settings(defaults)

        data = json.loads(self.path.read_text(encoding="utf-8"))
        return self._public_settings(WorkspaceSettings.model_validate({**defaults.model_dump(), **data}))

    def get_private(self) -> WorkspaceSettings:
        defaults = self._default_settings()
        if not self.path.exists():
            return defaults

        data = json.loads(self.path.read_text(encoding="utf-8"))
        return WorkspaceSettings.model_validate({**defaults.model_dump(), **data})

    def save(self, workspace_settings: WorkspaceSettings) -> WorkspaceSettings:
        current = self.get_private()
        api_key = workspace_settings.openai_api_key.strip() or current.openai_api_key
        normalized = workspace_settings.model_copy(
            update={
                "openai_api_key": api_key,
                "openai_api_key_set": bool(api_key),
                "channel_url": workspace_settings.channel_urls[0] if workspace_settings.channel_urls else "",
                "channel_urls": workspace_settings.channel_urls,
                "openai_base_url": workspace_settings.openai_base_url.rstrip("/"),
                "openai_translation_model": workspace_settings.openai_translation_model.strip(),
                "openai_analysis_model": workspace_settings.openai_analysis_model.strip(),
            }
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(normalized.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self._public_settings(normalized)

    def _default_settings(self) -> WorkspaceSettings:
        return WorkspaceSettings.model_construct(
            channel_url="",
            channel_urls=[],
            browser_engine=self._normalized_browser_engine(),
            browser_headless=self.settings.browser_headless,
            browser_path=self.settings.browser_path or "",
            browser_debug_port=self.settings.browser_debug_port,
            browser_cdp_url=self.settings.browser_cdp_url,
            openai_base_url=self.settings.openai_base_url.rstrip("/"),
            openai_translation_model=self.settings.openai_translation_model,
            openai_analysis_model=self.settings.openai_analysis_model or self.settings.openai_translation_model,
            openai_api_key=self.settings.openai_api_key or "",
            openai_api_key_set=bool(self.settings.openai_api_key),
            monitor_enabled=False,
            monitor_interval_minutes=180,
            monitor_auto_analyze=False,
            monitor_auto_translate=False,
            monitor_min_views=0,
        )

    def _normalized_browser_engine(self) -> Literal["playwright", "drission", "cdp"]:
        engine = self.settings.browser_engine.strip().lower()
        if engine == "drissionpage":
            return "drission"
        if engine == "drission":
            return "drission"
        if engine == "cdp":
            return "cdp"
        return "playwright"

    def _public_settings(self, workspace_settings: WorkspaceSettings) -> WorkspaceSettings:
        return workspace_settings.model_copy(
            update={
                "openai_api_key": "",
                "openai_api_key_set": bool(workspace_settings.openai_api_key),
            }
        )
