from creator_agent.config import Settings


def test_settings_defaults_are_mysql_and_redis_ready():
    settings = Settings()

    assert settings.database_url.startswith("mysql+pymysql://")
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.app_name == "YouTube Creator Growth Agent"
