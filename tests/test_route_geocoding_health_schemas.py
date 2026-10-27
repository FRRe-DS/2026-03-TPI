from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

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


def test_route_estimate_deserializes_and_serializes_contract_fields() -> None:
    estimate = EstimacionRuta.model_validate(
        {
            "origen": {"latitud": -90, "longitud": -180},
            "destino": {"latitud": 90, "longitud": 180},
            "distancia_estimada_km": 0,
            "eta_minutos": 0,
            "calculado_en": "2026-10-27T15:04:05Z",
            "fuente": "proveedor_mapa",
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
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        EstimacionRuta.model_validate(payload)


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
