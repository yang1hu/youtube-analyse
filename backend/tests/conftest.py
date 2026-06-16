from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from creator_agent.db.base import Base


@pytest.fixture()
def db_session() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with SessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
def isolate_analysis_log(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("YCA_ANALYSIS_LOG_PATH", str(tmp_path / "analysis.jsonl"))
