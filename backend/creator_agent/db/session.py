from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from creator_agent.config import Settings


def build_session_factory(settings: Settings) -> sessionmaker[Session]:
    engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
