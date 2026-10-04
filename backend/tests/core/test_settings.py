import pytest
from pydantic import ValidationError
from sqlalchemy.engine.url import make_url

from app.core.config import Settings, settings

_LOCAL_TOKEN_MINUTES = 60 * 24 * 8
_DEPLOYED_TOKEN_MINUTES = 60 * 12


def test_pytest_uses_hvostun_test_database() -> None:
    assert settings.FASTAPI_ENV == "test"
    assert settings.postgres_db == "hvostun_test"
    assert make_url(str(settings.DATABASE_URL)).database == "hvostun_test"


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "SECRET_KEY": "k" * 32,
        "PROJECT_NAME": "Hvostun",
        "DATABASE_URL": (
            "postgresql://postgres:unique-db-password@localhost:5432/ignored"
        ),
        "FIRST_SUPERUSER": "admin@example.com",
        "FIRST_SUPERUSER_PASSWORD": "unique-superuser-password",
        "FASTAPI_ENV": "production",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def test_production_rejects_short_secret_key() -> None:
    with pytest.raises(ValidationError, match="32 bytes"):
        _settings(SECRET_KEY="k" * 31)


def test_production_rejects_known_local_secrets() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _settings(SECRET_KEY="local-dev-secret-change-me")
    with pytest.raises(ValidationError, match="FIRST_SUPERUSER_PASSWORD"):
        _settings(FIRST_SUPERUSER_PASSWORD="local-dev-password")
    with pytest.raises(ValidationError, match="DATABASE_URL password"):
        _settings(
            DATABASE_URL=(
                "postgresql://postgres:local-dev-postgres@localhost:5432/ignored"
            )
        )
    with pytest.raises(ValidationError, match="DATABASE_URL password"):
        _settings(
            DATABASE_URL=(
                "postgresql://hvostun_app:local-dev-app@localhost:5432/ignored"
            )
        )


def test_local_env_warns_instead_of_raising() -> None:
    with pytest.warns(UserWarning, match="known local default"):
        local = _settings(FASTAPI_ENV="development", SECRET_KEY="changethis")
    assert local.ACCESS_TOKEN_EXPIRE_MINUTES == _LOCAL_TOKEN_MINUTES


def test_is_deployed_only_for_staging_and_production() -> None:
    assert _settings(FASTAPI_ENV="staging").is_deployed
    assert _settings().is_deployed
    local = _settings(FASTAPI_ENV="development")
    assert not local.is_deployed
    assert not _settings(FASTAPI_ENV="test").is_deployed


def test_deployed_cookie_defaults_to_twelve_hours(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ACCESS_TOKEN_EXPIRE_MINUTES", raising=False)
    deployed = _settings(FASTAPI_ENV="staging")
    assert deployed.ACCESS_TOKEN_EXPIRE_MINUTES == _DEPLOYED_TOKEN_MINUTES


def test_explicit_cookie_ttl_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(_LOCAL_TOKEN_MINUTES))
    deployed = _settings()
    assert deployed.ACCESS_TOKEN_EXPIRE_MINUTES == _LOCAL_TOKEN_MINUTES
