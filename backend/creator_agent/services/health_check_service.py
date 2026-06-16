from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import httpx
from redis import Redis
from sqlalchemy import text

from creator_agent.config import Settings
from creator_agent.db.session import build_engine
from creator_agent.services.settings_service import WorkspaceSettingsService


class HealthCheckService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    def run_checks(self) -> dict[str, Any]:
        checks = [
            self._check_database(),
            self._check_redis(),
            self._check_command("yt_dlp", ["yt-dlp", "--version"], "yt-dlp"),
            self._check_command("ffmpeg", ["ffmpeg", "-version"], "ffmpeg"),
            self._check_llm(),
            self._check_browser_cdp(),
            self._check_cache(),
            self._check_local_access(),
        ]
        failed = sum(1 for check in checks if check["status"] == "failed")
        warnings = sum(1 for check in checks if check["status"] in {"warning", "skipped"})
        status = "failed" if failed else "degraded" if warnings else "ok"
        return {"summary": {"status": status, "failed": failed, "warnings": warnings}, "checks": checks}

    def _check_database(self) -> dict[str, str]:
        if not self.settings.database_url:
            return self._result("mysql", "MySQL", "skipped", "Database URL is not configured.")
        try:
            engine = build_engine(self.settings)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return self._result("mysql", "MySQL", "ok", "Database connection is healthy.")
        except Exception as exc:
            return self._result("mysql", "MySQL", "failed", f"Database check failed: {exc}")

    def _check_redis(self) -> dict[str, str]:
        if not self.settings.redis_url:
            return self._result("redis", "Redis", "skipped", "Redis URL is not configured.")
        if not self._is_explicitly_configured("YCA_REDIS_URL"):
            return self._result("redis", "Redis", "skipped", "Redis is optional in local manual-run mode.")
        try:
            client = Redis.from_url(self.settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
            client.ping()
            return self._result("redis", "Redis", "ok", "Redis is reachable on the configured URL.")
        except Exception as exc:
            return self._result("redis", "Redis", "failed", f"Redis check failed: {exc}")

    def _check_command(self, key: str, command: list[str], label: str) -> dict[str, str]:
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=3, check=False)
        except FileNotFoundError:
            return self._result(key, label, "failed", f"{label} is not installed or not on PATH.")
        except Exception as exc:
            return self._result(key, label, "failed", f"{label} check failed: {exc}")
        if completed.returncode == 0:
            first_line = (completed.stdout or completed.stderr).splitlines()[0]
            return self._result(key, label, "ok", f"{label} is available: {first_line}")
        return self._result(key, label, "failed", f"{label} returned exit code {completed.returncode}.")

    def _check_llm(self) -> dict[str, str]:
        workspace_settings = WorkspaceSettingsService(self.settings).get_private()
        api_key = workspace_settings.openai_api_key or self.settings.openai_api_key
        base_url = (workspace_settings.openai_base_url or self.settings.openai_base_url).rstrip("/")
        if not api_key:
            return self._result("llm", "LLM", "warning", "API key is not configured; analysis will fall back or fail.")
        try:
            response = httpx.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=20,
            )
        except Exception as exc:
            return self._result("llm", "LLM", "failed", f"LLM endpoint is not reachable: {exc}")
        if response.status_code < 400:
            return self._result("llm", "LLM", "ok", "LLM endpoint accepted the configured key.")
        if response.status_code == 401:
            return self._result("llm", "LLM", "failed", "LLM endpoint rejected the configured API key.")
        return self._result("llm", "LLM", "failed", f"LLM endpoint returned HTTP {response.status_code}.")

    def _check_browser_cdp(self) -> dict[str, str]:
        workspace_settings = WorkspaceSettingsService(self.settings).get_private()
        if workspace_settings.browser_engine != "cdp":
            return self._result("browser_cdp", "Browser/CDP", "skipped", "CDP is not the selected browser mode.")
        try:
            response = httpx.get(f"{workspace_settings.browser_cdp_url.rstrip('/')}/json/version", timeout=2)
        except Exception as exc:
            return self._result("browser_cdp", "Browser/CDP", "failed", f"CDP endpoint is not reachable: {exc}")
        if response.status_code < 400:
            return self._result("browser_cdp", "Browser/CDP", "ok", "CDP endpoint is reachable.")
        return self._result("browser_cdp", "Browser/CDP", "failed", f"CDP endpoint returned HTTP {response.status_code}.")

    def _check_cache(self) -> dict[str, str]:
        paths = [
            Path(self.settings.transcript_cache_dir),
            Path(self.settings.translation_cache_dir),
            Path(self.settings.sample_cache_dir),
        ]
        try:
            for path in paths:
                path.mkdir(parents=True, exist_ok=True)
            return self._result("cache", "Cache", "ok", "Runtime cache directories are writable.")
        except Exception as exc:
            return self._result("cache", "Cache", "failed", f"Cache directories are not writable: {exc}")

    def _check_local_access(self) -> dict[str, str]:
        if self.settings.allow_remote_access:
            return self._result(
                "local_access",
                "Local Access Guard",
                "warning",
                "Remote access is explicitly enabled; only use this on a trusted network.",
            )
        return self._result("local_access", "Local Access Guard", "ok", "Remote access is disabled by default.")

    def _result(self, key: str, label: str, status: str, message: str) -> dict[str, str]:
        return {"key": key, "label": label, "status": status, "message": message}

    def _is_explicitly_configured(self, env_name: str) -> bool:
        return bool(os.getenv(env_name))
