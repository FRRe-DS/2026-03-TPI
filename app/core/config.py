from functools import lru_cache

from pydantic import Field, PositiveFloat, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "M4 - Ubicación y Disponibilidad"
    database_url: str | None = None
    location_ttl_seconds: int = Field(default=30, ge=30, le=30)
    reservation_ttl_seconds: PositiveInt | None = None
    default_search_radius_km: PositiveFloat = 5.0
    max_candidates: int = Field(default=20, ge=1, le=100)
    m3_timeout_seconds: PositiveFloat = 5.0
    maps_timeout_seconds: PositiveFloat = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
