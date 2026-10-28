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


def test_m3_client_settings_load_service_endpoint_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("M3_BASE_URL", "https://m3.example.test")
    monkeypatch.setenv("M3_SERVICE_TOKEN", "service-token")
    monkeypatch.setenv(
        "M3_ELIGIBILITY_PATH",
        "/drivers/{conductor_id}/eligibility",
    )
    monkeypatch.setenv("M3_TIMEOUT_SECONDS", "1.5")

    settings = Settings(_env_file=None)

    assert settings.m3_base_url == "https://m3.example.test"
    assert settings.m3_service_token == "service-token"
    assert settings.m3_eligibility_path == "/drivers/{conductor_id}/eligibility"
    assert settings.m3_timeout_seconds == 1.5


def test_m3_timeout_must_be_finite() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, m3_timeout_seconds=float("inf"))


def test_search_radius_limits_are_configurable_and_consistent() -> None:
    settings = Settings(
        _env_file=None,
        default_search_radius_km=5,
        max_search_radius_km=12,
        max_candidates=30,
    )

    assert settings.default_search_radius_km == 5
    assert settings.max_search_radius_km == 12
    assert settings.max_candidates == 30

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            default_search_radius_km=5,
            max_search_radius_km=4,
        )


def test_coverage_geojson_is_read_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = '{"type":"Polygon","coordinates":[]}'
    monkeypatch.setenv("COVERAGE_GEOJSON", document)

    assert Settings(_env_file=None).coverage_geojson == document
