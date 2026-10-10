import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401 -- registers models on Base.metadata
from app.config import settings
from app.db import Base

TEST_DB_NAME = "memorypalace_test"


def _admin_url() -> str:
    return settings.database_url.rsplit("/", 1)[0] + "/postgres"


def _test_db_url() -> str:
    return settings.database_url.rsplit("/", 1)[0] + f"/{TEST_DB_NAME}"


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    admin_engine = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": TEST_DB_NAME},
        ).first()
        if not exists:
            conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    admin_engine.dispose()

    engine = create_engine(_test_db_url())
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(engine)
    engine.dispose()
    yield


@pytest.fixture()
def db_session():
    engine = create_engine(_test_db_url())
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()
        session.close()
        engine.dispose()
