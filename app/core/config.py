from functools import lru_cache
import math

from pydantic import (
    Field,
    PositiveFloat,
    PositiveInt,
    field_validator,
    model_validator,
)
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
    redis_url: str | None = None
    location_ttl_seconds: int = Field(default=30, ge=30, le=30)
    reservation_ttl_seconds: PositiveInt | None = None
    default_search_radius_km: PositiveFloat = 5.0
    max_search_radius_km: PositiveFloat = 20.0
    max_candidates: int = Field(default=20, ge=1, le=100)
    proximity_eta_degradation_enabled: bool = True
    coverage_geojson: str | None = None
    m3_timeout_seconds: PositiveFloat = 5.0
    m3_base_url: str | None = None
    m3_service_token: str | None = None
    m3_eligibility_path: str | None = None
    maps_timeout_seconds: PositiveFloat = 5.0

    @field_validator(
        "default_search_radius_km",
        "max_search_radius_km",
        "m3_timeout_seconds",
        "maps_timeout_seconds",
    )
    @classmethod
    def positive_float_settings_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("Los valores numéricos de configuración deben ser finitos.")
        return value

    @model_validator(mode="after")
    def validate_m3_configuration(self) -> "Settings":
        if self.max_search_radius_km < self.default_search_radius_km:
            raise ValueError(
                "MAX_SEARCH_RADIUS_KM no puede ser menor que "
                "DEFAULT_SEARCH_RADIUS_KM."
            )
        m3_values = (
            self.m3_base_url,
            self.m3_service_token,
            self.m3_eligibility_path,
        )
        if any(m3_values) and not all(m3_values):
            raise ValueError(
                "M3_BASE_URL, M3_SERVICE_TOKEN y M3_ELIGIBILITY_PATH "
                "deben configurarse juntos."
            )
        if self.m3_eligibility_path is not None:
            if not self.m3_eligibility_path.startswith("/"):
                raise ValueError("M3_ELIGIBILITY_PATH debe ser una ruta absoluta.")
            if "{conductor_id}" not in self.m3_eligibility_path:
                raise ValueError(
                    "M3_ELIGIBILITY_PATH debe incluir {conductor_id}; "
                    "la ruta debe corresponder al contrato desplegado de M3."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
