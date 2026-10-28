import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from geopy.exc import GeocoderTimedOut
from pydantic import ValidationError

from app.clients.geocoding import NominatimGeocodingAdapter
from app.core.errors import DependencyTimeoutError, DependencyUnavailableError
from app.schemas.schemas import (
    CoincidenciaGeocodificacion,
    ConsultaGeocodificacion,
    EstimacionRuta,
    FuenteEstimacion,
    LivenessResponse,
    PuntoGeografico,
    ReadinessResponse,
    ResultadoGeocodificacion,
)
from app.servicios.route_estimation import estimate_route


def test_route_estimate_deserializes_and_serializes_contract_fields() -> None:
    estimate = EstimacionRuta.model_validate(
        {
            "origen": {"latitud": -90, "longitud": -180},
            "destino": {"latitud": 90, "longitud": 180},
            "distancia_estimada_km": 0,
            "eta_minutos": 0,
            "calculado_en": "2026-10-27T15:04:05Z",
            "fuente": "proveedor_mapa",
            "viable": True,
        }
    )

    assert estimate.fuente is FuenteEstimacion.PROVEEDOR_MAPA
    assert estimate.calculado_en == datetime(
        2026, 10, 27, 15, 4, 5, tzinfo=timezone.utc
    )
    assert estimate.model_dump(mode="json") == {
        "origen": {"latitud": -90, "longitud": -180},
        "destino": {"latitud": 90, "longitud": 180},
        "distancia_estimada_km": 0,
        "eta_minutos": 0,
        "calculado_en": "2026-10-27T15:04:05Z",
        "fuente": "proveedor_mapa",
        "viable": True,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("distancia_estimada_km", -0.01),
        ("eta_minutos", -1),
        ("fuente", "unknown"),
        ("calculado_en", "2026-10-27T15:04:05"),
    ],
)
def test_route_estimate_rejects_invalid_values(field: str, value: object) -> None:
    payload: dict[str, object] = {
        "origen": {"latitud": 0, "longitud": 0},
        "destino": {"latitud": 1, "longitud": 1},
        "distancia_estimada_km": 1.5,
        "eta_minutos": 5,
        "calculado_en": "2026-10-27T15:04:05Z",
        "fuente": "estimacion_local",
        "viable": True,
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        EstimacionRuta.model_validate(payload)


def test_route_adapter_accepts_provider_and_rejects_unapproved_local_fallback() -> None:
    origin = PuntoGeografico(latitud=0.1, longitud=0.1)
    destination = PuntoGeografico(latitud=0.2, longitud=0.2)

    async def route_provider(request_origin, request_destination, vehicle):
        return {
            "origen": request_origin.model_dump(),
            "destino": request_destination.model_dump(),
            "distancia_estimada_km": 1.8,
            "eta_minutos": 6,
            "calculado_en": "2026-10-27T15:04:05Z",
            "fuente": "proveedor_mapa",
            "viable": True,
        }

    result = asyncio.run(
        estimate_route(
            route_provider,
            origin,
            destination,
            None,
            timeout_seconds=1,
        )
    )
    assert result.distancia_estimada_km == 1.8
    assert result.fuente is FuenteEstimacion.PROVEEDOR_MAPA

    async def local_fallback(request_origin, request_destination, vehicle):
        return {
            "origen": request_origin.model_dump(),
            "destino": request_destination.model_dump(),
            "distancia_estimada_km": 1.8,
            "eta_minutos": 6,
            "calculado_en": "2026-10-27T15:04:05Z",
            "fuente": "estimacion_local",
            "viable": True,
        }

    with pytest.raises(DependencyUnavailableError):
        asyncio.run(
            estimate_route(
                local_fallback,
                origin,
                destination,
                None,
                timeout_seconds=1,
            )
        )


def test_route_adapter_enforces_configured_timeout() -> None:
    origin = PuntoGeografico(latitud=0.1, longitud=0.1)
    destination = PuntoGeografico(latitud=0.2, longitud=0.2)

    async def slow_provider(request_origin, request_destination, vehicle):
        await asyncio.sleep(0.05)

    with pytest.raises(DependencyTimeoutError):
        asyncio.run(
            estimate_route(
                slow_provider,
                origin,
                destination,
                None,
                timeout_seconds=0.001,
            )
        )


@pytest.mark.parametrize(
    ("latitud", "longitud"),
    [
        (-90, -180),
        (90, 180),
    ],
)
def test_geographic_point_accepts_wgs84_limits(latitud: float, longitud: float) -> None:
    point = PuntoGeografico(latitud=latitud, longitud=longitud)

    assert point.latitud == latitud
    assert point.longitud == longitud


@pytest.mark.parametrize(
    ("latitud", "longitud"),
    [
        (-90.01, 0),
        (90.01, 0),
        (0, -180.01),
        (0, 180.01),
    ],
)
def test_geographic_point_rejects_coordinates_outside_wgs84(
    latitud: float, longitud: float
) -> None:
    with pytest.raises(ValidationError):
        PuntoGeografico(latitud=latitud, longitud=longitud)


def test_geocoding_request_validates_contract_lengths_and_extra_fields() -> None:
    query = ConsultaGeocodificacion.model_validate(
        {"direccion": "Av. Corrientes 1000", "localidad": "Resistencia", "pais": "AR"}
    )

    assert query.model_dump() == {
        "direccion": "Av. Corrientes 1000",
        "localidad": "Resistencia",
        "pais": "AR",
    }
    with pytest.raises(ValidationError):
        ConsultaGeocodificacion(direccion="", pais="AR")
    with pytest.raises(ValidationError):
        ConsultaGeocodificacion(direccion="Calle 1", pais="ARG")
    with pytest.raises(ValidationError):
        ConsultaGeocodificacion(direccion="Calle 1", pais="AR", latitud=0)
    with pytest.raises(ValidationError):
        ConsultaGeocodificacion(direccion="   ", pais="AR")
    with pytest.raises(ValidationError):
        ConsultaGeocodificacion(direccion="Calle 1", pais="1!")


def test_geocoding_result_accepts_empty_list() -> None:
    result = ResultadoGeocodificacion.model_validate({"coincidencias": []})

    assert result.coincidencias == []
    assert result.model_dump(mode="json") == {"coincidencias": []}


def test_geocoding_result_preserves_multiple_ambiguous_matches() -> None:
    result = ResultadoGeocodificacion.model_validate(
        {
            "coincidencias": [
                {
                    "latitud": -27.4512,
                    "longitud": -58.9866,
                    "etiqueta": "Plaza 25 de Mayo, Resistencia",
                    "confianza": 0.9,
                },
                {
                    "latitud": -27.46,
                    "longitud": -58.98,
                    "etiqueta": "Plaza 25 de Mayo, otra coincidencia",
                },
            ]
        }
    )

    assert len(result.coincidencias) == 2
    assert result.coincidencias[0].confianza == 0.9
    assert result.coincidencias[1].confianza is None


@pytest.mark.parametrize(
    "payload",
    [
        {
            "latitud": -90.1,
            "longitud": 0,
            "etiqueta": "Fuera de rango",
        },
        {
            "latitud": 0,
            "longitud": 0,
            "etiqueta": "Confianza inválida",
            "confianza": 1.1,
        },
        {
            "latitud": 0,
            "longitud": 0,
            "etiqueta": "Campo extra",
            "conductor_id": "018f1f20-7b4a-7cc2-9d41-66382a18cc5a",
        },
    ],
)
def test_geocoding_result_rejects_invalid_match(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CoincidenciaGeocodificacion.model_validate(payload)


@pytest.mark.parametrize(
    ("provider_results", "expected_count"),
    [
        ([], 0),
        (
            [
                SimpleNamespace(
                    latitude=-27.45,
                    longitude=-58.98,
                    address="Plaza, Resistencia",
                    raw={"display_name": "Plaza, Resistencia"},
                )
            ],
            1,
        ),
        (
            [
                SimpleNamespace(
                    latitude=-27.45,
                    longitude=-58.98,
                    address="Primera",
                    raw={"display_name": "Primera"},
                ),
                SimpleNamespace(
                    latitude=-27.46,
                    longitude=-58.97,
                    address="Segunda",
                    raw={"display_name": "Segunda"},
                ),
            ],
            2,
        ),
    ],
)
def test_nominatim_adapter_maps_zero_one_and_multiple_matches(
    provider_results: list[object], expected_count: int
) -> None:
    class FakeGeocoder:
        def geocode(self, query, **kwargs):
            assert query == "Plaza 25 de Mayo, Resistencia, AR"
            assert kwargs["country_codes"] == "ar"
            assert kwargs["exactly_one"] is False
            return provider_results

    adapter = NominatimGeocodingAdapter(
        timeout_seconds=1,
        user_agent="test-agent",
        min_delay_seconds=0.001,
        geocoder=FakeGeocoder(),
    )
    query = ConsultaGeocodificacion(
        direccion=" Plaza 25 de Mayo ",
        localidad=" Resistencia ",
        pais="ar",
    )

    result = asyncio.run(adapter.geocode(query))

    assert len(result.coincidencias) == expected_count
    assert all(match.etiqueta for match in result.coincidencias)


def test_nominatim_adapter_maps_timeout_and_malformed_results() -> None:
    class TimeoutGeocoder:
        def geocode(self, query, **kwargs):
            raise GeocoderTimedOut("provider timeout")

    timed_out = NominatimGeocodingAdapter(
        timeout_seconds=1,
        user_agent="test-agent",
        min_delay_seconds=0.001,
        geocoder=TimeoutGeocoder(),
    )
    query = ConsultaGeocodificacion(direccion="Calle 1", pais="AR")
    with pytest.raises(DependencyTimeoutError):
        asyncio.run(timed_out.geocode(query))

    class MalformedGeocoder:
        def geocode(self, query, **kwargs):
            return [SimpleNamespace(latitude=100, longitude=0, address="Invalid")]

    malformed = NominatimGeocodingAdapter(
        timeout_seconds=1,
        user_agent="test-agent",
        min_delay_seconds=0.001,
        geocoder=MalformedGeocoder(),
    )
    with pytest.raises(DependencyUnavailableError):
        asyncio.run(malformed.geocode(query))


@pytest.mark.parametrize(
    ("schema", "expected_status", "invalid_status"),
    [
        (LivenessResponse, "UP", "DOWN"),
        (ReadinessResponse, "READY", "NOT_READY"),
    ],
)
def test_health_response_enforces_contract_status(
    schema: type[LivenessResponse] | type[ReadinessResponse],
    expected_status: str,
    invalid_status: str,
) -> None:
    response = schema.model_validate({"status": expected_status})

    assert response.model_dump(mode="json") == {"status": expected_status}
    with pytest.raises(ValidationError):
        schema.model_validate({"status": invalid_status})
    assert schema.model_validate(
        {"status": expected_status, "details": "extension"}
    ).model_dump() == {"status": expected_status}
