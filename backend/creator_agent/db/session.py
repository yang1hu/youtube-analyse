from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy.orm import Session, sessionmaker

from creator_agent.config import Settings
from creator_agent.db.base import Base


def build_engine(settings: Settings):
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


def initialize_database(settings: Settings):
    import creator_agent.db.models  # noqa: F401

    engine = build_engine(settings)
    Base.metadata.create_all(engine)
    _upgrade_existing_schema(engine)
    return engine


def _upgrade_existing_schema(engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if engine.dialect.name not in {"mysql", "mariadb"}:
        return

    with engine.begin() as connection:
        if "videos" in table_names:
            video_columns = {str(column.get("name")) for column in inspector.get_columns("videos")}
            if "published_text" not in video_columns:
                connection.exec_driver_sql("ALTER TABLE videos ADD COLUMN published_text VARCHAR(255) NULL")
            if "is_recent_upload" not in video_columns:
                connection.exec_driver_sql("ALTER TABLE videos ADD COLUMN is_recent_upload BOOLEAN NOT NULL DEFAULT FALSE")

        if "video_reports" in table_names:
            report_columns = {str(column.get("name")) for column in inspector.get_columns("video_reports")}
            if "external_id" not in report_columns:
                connection.exec_driver_sql("ALTER TABLE video_reports ADD COLUMN external_id VARCHAR(255) NULL")
                connection.exec_driver_sql("CREATE UNIQUE INDEX ix_video_reports_external_id ON video_reports (external_id)")
            connection.exec_driver_sql("ALTER TABLE video_reports MODIFY COLUMN title_hook TEXT NULL")
            connection.exec_driver_sql("ALTER TABLE video_reports MODIFY COLUMN opening_hook TEXT NULL")
            indexes = inspector.get_indexes("video_reports")
            index_names = {str(index.get("name")) for index in indexes}
            for index in indexes:
                if index.get("name") == "ix_video_reports_video_id" and index.get("unique"):
                    if "idx_video_reports_video_id" not in index_names:
                        connection.exec_driver_sql("CREATE INDEX idx_video_reports_video_id ON video_reports (video_id)")
                    connection.exec_driver_sql("ALTER TABLE video_reports DROP INDEX ix_video_reports_video_id")
                    break

        if "analysis_jobs" in table_names:
            job_columns = {str(column.get("name")) for column in inspector.get_columns("analysis_jobs")}
            if "external_id" not in job_columns:
                connection.exec_driver_sql("ALTER TABLE analysis_jobs ADD COLUMN external_id VARCHAR(255) NULL")
                connection.exec_driver_sql("CREATE UNIQUE INDEX ix_analysis_jobs_external_id ON analysis_jobs (external_id)")

        if "idea_cards" in table_names:
            idea_columns = {str(column.get("name")) for column in inspector.get_columns("idea_cards")}
            if "external_id" not in idea_columns:
                connection.exec_driver_sql("ALTER TABLE idea_cards ADD COLUMN external_id VARCHAR(255) NULL")
                connection.exec_driver_sql("CREATE UNIQUE INDEX ix_idea_cards_external_id ON idea_cards (external_id)")

        for table_name, index_specs in {
            "channels": [
                ("ix_channels_updated_at", ["updated_at"]),
                ("ix_channels_created_at", ["created_at"]),
            ],
            "videos": [
                ("ix_videos_created_at", ["created_at"]),
                ("ix_videos_updated_at", ["updated_at"]),
            ],
            "analysis_jobs": [
                ("ix_analysis_jobs_created_at", ["created_at"]),
                ("ix_analysis_jobs_updated_at", ["updated_at"]),
            ],
            "video_reports": [
                ("ix_video_reports_created_at", ["created_at"]),
                ("ix_video_reports_updated_at", ["updated_at"]),
            ],
            "idea_cards": [
                ("ix_idea_cards_created_at", ["created_at"]),
                ("ix_idea_cards_updated_at", ["updated_at"]),
            ],
            "sample_analyses": [
                ("ix_sample_analyses_created_at", ["created_at"]),
                ("ix_sample_analyses_updated_at", ["updated_at"]),
            ],
            "style_profiles": [
                ("ix_style_profiles_created_at", ["created_at"]),
                ("ix_style_profiles_updated_at", ["updated_at"]),
            ],
            "copy_drafts": [
                ("ix_copy_drafts_created_at", ["created_at"]),
                ("ix_copy_drafts_updated_at", ["updated_at"]),
            ],
            "script_drafts": [
                ("ix_script_drafts_created_at", ["created_at"]),
                ("ix_script_drafts_updated_at", ["updated_at"]),
            ],
        }.items():
            if table_name not in table_names:
                continue
            existing_indexes = {str(index.get("name")) for index in inspector.get_indexes(table_name)}
            for index_name, columns in index_specs:
                if index_name in existing_indexes:
                    continue
                column_list = ", ".join(columns)
                connection.exec_driver_sql(f"CREATE INDEX {index_name} ON {table_name} ({column_list})")


def build_session_factory(settings: Settings) -> sessionmaker[Session]:
    engine = initialize_database(settings)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
