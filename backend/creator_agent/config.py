from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_name: str = "YouTube Creator Growth Agent"
    database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"
    default_model: str = "local-stub"
    browser_engine: str = "playwright"
    browser_path: str | None = None
    browser_debug_port: int | None = None
    browser_cdp_url: str = "http://127.0.0.1:9222"
    browser_headless: bool = True
    workspace_settings_path: str = str(BACKEND_DIR / ".runtime" / "workspace-settings.json")
    workspace_data_path: str = str(BACKEND_DIR / ".runtime" / "workspace-data.json")
    analysis_log_path: str = str(BACKEND_DIR / ".runtime" / "logs" / "analysis.jsonl")
    transcript_cache_dir: str = str(BACKEND_DIR / ".runtime" / "transcripts")
    translation_cache_dir: str = str(BACKEND_DIR / ".runtime" / "translations")
    sample_cache_dir: str = str(BACKEND_DIR / ".runtime" / "samples")
    inkos_command: str = "inkos"
    inkos_project_dir: str = str(BACKEND_DIR / ".runtime" / "inkos")
    inkos_timeout_seconds: int = 600
    openai_api_key: str | None = None
    openai_base_url: str = "https://www.inroi.shop/v1"
    openai_translation_model: str = "gpt-5.5"
    openai_analysis_model: str | None = "gpt-5.5"
    allow_remote_access: bool = False

    model_config = SettingsConfigDict(env_prefix="YCA_", env_file=BACKEND_DIR / ".env", extra="ignore")
