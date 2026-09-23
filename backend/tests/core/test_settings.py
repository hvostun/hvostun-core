from sqlalchemy.engine.url import make_url

from app.core.config import settings


def test_pytest_uses_hvostun_test_database() -> None:
    assert settings.FASTAPI_ENV == "test"
    assert settings.postgres_db == "hvostun_test"
    assert make_url(str(settings.DATABASE_URL)).database == "hvostun_test"
