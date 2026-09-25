from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlmodel import Session

import tests.envbootstrap  # noqa: F401
from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app


def _ensure_test_database() -> None:
    url = make_url(str(settings.DATABASE_URL))
    db_name = url.database
    assert db_name == "hvostun_test"
    admin_engine = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            ).scalar()
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        admin_engine.dispose()


def _upgrade_test_database() -> None:
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    config = Config(str(ini))
    command.upgrade(config, "head")


_ensure_test_database()
_upgrade_test_database()


def _truncate_test_data(session: Session) -> None:
    session.execute(
        text(
            """
            TRUNCATE TABLE
                session_recomendations,
                answer_events,
                survey_sessions,
                surveys_questions,
                survey_versions,
                placement_events,
                dog_chips,
                consents,
                questions,
                scales,
                recommendations,
                dogs,
                shelters,
                owners,
                surveys,
                users
            RESTART IDENTITY CASCADE
            """
        )
    )
    session.commit()


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    with Session(engine) as session:
        _truncate_test_data(session)
        init_db(session)
        yield session
        _truncate_test_data(session)


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c
