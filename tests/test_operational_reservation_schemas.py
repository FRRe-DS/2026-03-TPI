from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.schemas import (
    CambioReservaTemporal,
    Candidato,
    EstadoOperativo,
    EstadoOperativoRegistrado,
    EstadoTemporal,
    ResultadoBusquedaConductores,
    ResultadoReservaTemporal,
    TipoVehiculo,
)

DRIVER_ID = UUID("018f1f20-7b4a-7cc2-9d41-66382a18cc5a")
REQUEST_ID = UUID("018f1f20-a128-739e-8af1-4caa35108a91")
NOW = datetime(2026, 10, 27, 15, 4, 5, tzinfo=timezone.utc)


def test_estado_operativo_parses_optional_event_fields_and_serializes_enum_types() -> None:
    event = EstadoOperativo.model_validate(
        {
            "event_id": str(REQUEST_ID),
            "connected": True,
            "available": True,
            "timestamp_evento": "2026-10-27T15:04:05Z",
        }
    )

    assert event.event_id == REQUEST_ID
    assert event.timestamp_evento == NOW
    assert event.model_dump(mode="json") == {
        "event_id": str(REQUEST_ID),
        "connected": True,
        "available": True,
        "timestamp_evento": "2026-10-27T15:04:05Z",
    }


def test_estado_operativo_requires_connected_and_available() -> None:
    with pytest.raises(ValidationError):
        EstadoOperativo.model_validate({"connected": True})


@pytest.mark.parametrize(
    "timestamp",
    ["2026-10-27T15:04:05", "2026-10-27T12:04:05-03:00"],
)
def test_estado_operativo_rejects_non_utc_timestamp(timestamp: str) -> None:
    with pytest.raises(ValidationError):
        EstadoOperativo(
            connected=True,
            available=True,
            timestamp_evento=timestamp,
        )


def test_estado_operativo_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        EstadoOperativo(connected=True, available=True, latitud=-27.4)


def test_estado_operativo_response_requires_fields_and_enforces_availability() -> None:
    response = EstadoOperativoRegistrado.model_validate(
        {
            "conductor_id": str(DRIVER_ID),
            "connected": False,
            "available": False,
            "recibido_en": "2026-10-27T15:04:05Z",
        }
    )

    assert response.conductor_id == DRIVER_ID
    assert response.model_dump(mode="json")["recibido_en"] == "2026-10-27T15:04:05Z"
    with pytest.raises(ValidationError):
        EstadoOperativoRegistrado(
            conductor_id=DRIVER_ID,
            connected=False,
            available=True,
            recibido_en=NOW,
        )


def test_candidato_round_trips_without_optional_eta() -> None:
    candidate = Candidato.model_validate(
        {
            "conductor_id": str(DRIVER_ID),
            "distancia_origen_km": 0.42,
            "tipo_vehiculo": "AUTO",
        }
    )

    assert candidate.tipo_vehiculo is TipoVehiculo.AUTO
    assert candidate.eta_retiro_minutos is None
    assert candidate.model_dump(mode="json") == {
        "conductor_id": str(DRIVER_ID),
        "distancia_origen_km": 0.42,
        "eta_retiro_minutos": None,
        "tipo_vehiculo": "AUTO",
    }


@pytest.mark.parametrize("coordinate_field", ["latitud", "longitud"])
def test_candidato_forbids_driver_coordinates(coordinate_field: str) -> None:
    with pytest.raises(ValidationError):
        Candidato.model_validate(
            {
                "conductor_id": str(DRIVER_ID),
                "distancia_origen_km": 0.42,
                "tipo_vehiculo": "AUTO",
                coordinate_field: -27.45,
            }
        )


def test_candidato_requires_fields_and_valid_enum_and_ranges() -> None:
    with pytest.raises(ValidationError):
        Candidato.model_validate({"conductor_id": str(DRIVER_ID)})

    with pytest.raises(ValidationError):
        Candidato(
            conductor_id=DRIVER_ID,
            distancia_origen_km=-0.1,
            tipo_vehiculo="BICYCLE",
        )

    with pytest.raises(ValidationError):
        Candidato(
            conductor_id=DRIVER_ID,
            distancia_origen_km=0.1,
            eta_retiro_minutos=-1,
            tipo_vehiculo="MOTO",
        )


def test_search_result_serializes_candidate_list_and_requires_result_fields() -> None:
    result = ResultadoBusquedaConductores.model_validate(
        {
            "conductores": [
                {
                    "conductor_id": str(DRIVER_ID),
                    "distancia_origen_km": 1.25,
                    "eta_retiro_minutos": 4,
                    "tipo_vehiculo": "MOTO",
                }
            ],
            "radio_aplicado_km": 5,
            "generado_en": "2026-10-27T15:04:05Z",
        }
    )

    assert result.conductores[0].tipo_vehiculo is TipoVehiculo.MOTO
    assert result.model_dump(mode="json")["conductores"][0]["tipo_vehiculo"] == "MOTO"
    with pytest.raises(ValidationError):
        ResultadoBusquedaConductores(conductores=[], radio_aplicado_km=0)


def test_reservation_change_requires_fields_and_valid_enum() -> None:
    change = CambioReservaTemporal.model_validate(
        {
            "estado_temporal": "RESERVADO",
            "solicitud_id": str(REQUEST_ID),
        }
    )

    assert change.estado_temporal is EstadoTemporal.RESERVADO
    assert change.model_dump(mode="json") == {
        "estado_temporal": "RESERVADO",
        "solicitud_id": str(REQUEST_ID),
    }

    with pytest.raises(ValidationError):
        CambioReservaTemporal(estado_temporal="RESERVADO")
    with pytest.raises(ValidationError):
        CambioReservaTemporal(estado_temporal="PENDING", solicitud_id=REQUEST_ID)
    with pytest.raises(ValidationError):
        CambioReservaTemporal(
            estado_temporal="LIBERADO",
            solicitud_id=REQUEST_ID,
            conductor_id=DRIVER_ID,
        )


def test_reservation_result_requires_fields_and_serializes_optional_fields() -> None:
    result = ResultadoReservaTemporal.model_validate(
        {
            "conductor_id": str(DRIVER_ID),
            "solicitud_id": str(REQUEST_ID),
            "estado_temporal": "RESERVADO",
            "actualizado_en": "2026-10-27T15:04:05Z",
            "expira_en": "2026-10-27T15:09:05Z",
            "idempotente": False,
        }
    )

    assert result.estado_temporal is EstadoTemporal.RESERVADO
    assert result.expira_en is not None
    assert result.model_dump(mode="json")["idempotente"] is False
    with pytest.raises(ValidationError):
        ResultadoReservaTemporal(
            conductor_id=DRIVER_ID,
            solicitud_id=REQUEST_ID,
            estado_temporal="RESERVADO",
        )
