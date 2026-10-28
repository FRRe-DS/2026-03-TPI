import asyncio
from collections.abc import Sequence
import math
import threading
import time
from typing import Protocol

from geopy.exc import GeocoderTimedOut, GeopyError
from geopy.geocoders import Nominatim
from pydantic import ValidationError

from app.core.errors import DependencyTimeoutError, DependencyUnavailableError
from app.schemas.schemas import (
    CoincidenciaGeocodificacion,
    ConsultaGeocodificacion,
    ResultadoGeocodificacion,
)


class GeocodingResult(Protocol):
    latitude: float
    longitude: float
    address: str
    raw: dict[str, object]


class Geocoder(Protocol):
    def geocode(
        self,
        query: str,
        *,
        country_codes: str,
        exactly_one: bool,
        limit: int,
        timeout: float,
    ) -> Sequence[GeocodingResult] | GeocodingResult | None: ...


class NominatimGeocodingAdapter:
    def __init__(
        self,
        *,
        timeout_seconds: float,
        user_agent: str,
        min_delay_seconds: float = 1.1,
        geocoder: Geocoder | None = None,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("user_agent no puede estar vacío.")
        if (
            not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
            or not math.isfinite(min_delay_seconds)
            or min_delay_seconds <= 0
        ):
            raise ValueError("Timeout y demora mínima deben ser positivos.")
        self._timeout_seconds = timeout_seconds
        self._min_delay_seconds = min_delay_seconds
        self._geocoder = geocoder or Nominatim(
            user_agent=user_agent,
            timeout=timeout_seconds,
        )
        self._rate_limit_lock = threading.Lock()
        self._last_request_at = 0.0

    async def geocode(
        self, query: ConsultaGeocodificacion
    ) -> ResultadoGeocodificacion:
        address = ", ".join(
            part
            for part in (query.direccion, query.localidad, query.pais)
            if part is not None
        )
        try:
            results = await asyncio.to_thread(self._geocode_sync, address, query.pais)
        except (GeocoderTimedOut, TimeoutError) as error:
            raise DependencyTimeoutError(
                "El proveedor de geocodificación excedió el tiempo de espera."
            ) from error
        except GeopyError as error:
            raise DependencyUnavailableError(
                "El proveedor de geocodificación no está disponible."
            ) from error
        except (TypeError, ValueError, ValidationError) as error:
            raise DependencyUnavailableError(
                "El proveedor de geocodificación devolvió una respuesta inválida."
            ) from error

        if results is None:
            matches: Sequence[GeocodingResult] = ()
        elif isinstance(results, Sequence) and not isinstance(results, (str, bytes)):
            matches = results
        else:
            matches = (results,)

        try:
            return ResultadoGeocodificacion(
                coincidencias=[
                    CoincidenciaGeocodificacion(
                        latitud=result.latitude,
                        longitud=result.longitude,
                        etiqueta=result.raw.get("display_name", result.address),
                    )
                    for result in matches
                ]
            )
        except (AttributeError, TypeError, ValidationError) as error:
            raise DependencyUnavailableError(
                "El proveedor de geocodificación devolvió una respuesta inválida."
            ) from error

    def _geocode_sync(
        self, address: str, country_code: str
    ) -> Sequence[GeocodingResult] | GeocodingResult | None:
        with self._rate_limit_lock:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < self._min_delay_seconds:
                time.sleep(self._min_delay_seconds - elapsed)
            try:
                return self._geocoder.geocode(
                    address,
                    country_codes=country_code.lower(),
                    exactly_one=False,
                    limit=10,
                    timeout=self._timeout_seconds,
                )
            finally:
                self._last_request_at = time.monotonic()
