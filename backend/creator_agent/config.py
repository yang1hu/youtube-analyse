from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "YouTube Creator Growth Agent"
    database_url: str = "mysql+pymysql://creator_agent:creator_agent@localhost:3306/creator_agent"
    redis_url: str = "redis://localhost:6379/0"
    default_model: str = "local-stub"

    model_config = SettingsConfigDict(env_prefix="YCA_", env_file=".env", extra="ignore")
