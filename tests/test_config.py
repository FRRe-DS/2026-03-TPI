import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_load_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = "postgresql+psycopg2://user:pass@localhost:5432/m4"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("LOCATION_TTL_SECONDS", "30")

    settings = Settings(_env_file=None)

    assert settings.database_url == database_url
    assert settings.location_ttl_seconds == 30


def test_location_ttl_cannot_override_constitutional_value() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, location_ttl_seconds=60)


def test_reservation_ttl_is_optional_until_agreed() -> None:
    assert Settings(_env_file=None).reservation_ttl_seconds is None


def test_redis_url_loads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    redis_url = "redis://redis:6379/0"
    monkeypatch.setenv("REDIS_URL", redis_url)

    assert Settings(_env_file=None).redis_url == redis_url
