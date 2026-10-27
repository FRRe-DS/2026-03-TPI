from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.schemas import ActualizarUbicacion, UbicacionRegistrada

CONDUCTOR_ID = UUID("018f1f20-7b4a-7cc2-9d41-66382a18cc5a")
TIMESTAMP = datetime(2026, 10, 20, 15, 4, 5, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("latitud", "longitud"),
    [
        (-90, -180),
        (90, 180),
        (0, 0),
    ],
)
def test_actualizar_ubicacion_accepts_wgs84_boundaries(
    latitud: float, longitud: float
) -> None:
    location = ActualizarUbicacion(
        conductor_id=CONDUCTOR_ID,
        latitud=latitud,
        longitud=longitud,
        timestamp_ubicacion=TIMESTAMP,
    )

    assert location.latitud == latitud
    assert location.longitud == longitud


@pytest.mark.parametrize(
    ("latitud", "longitud"),
    [
        (-90.0001, 0),
        (90.0001, 0),
        (0, -180.0001),
        (0, 180.0001),
    ],
)
def test_actualizar_ubicacion_rejects_coordinates_outside_wgs84(
    latitud: float, longitud: float
) -> None:
    with pytest.raises(ValidationError):
        ActualizarUbicacion(
            conductor_id=CONDUCTOR_ID,
            latitud=latitud,
            longitud=longitud,
            timestamp_ubicacion=TIMESTAMP,
        )


def test_actualizar_ubicacion_accepts_utc_timestamp_string() -> None:
    location = ActualizarUbicacion.model_validate(
        {
            "conductor_id": str(CONDUCTOR_ID),
            "latitud": -27.4512,
            "longitud": -58.9866,
            "timestamp_ubicacion": "2026-10-20T15:04:05Z",
        }
    )

    assert location.timestamp_ubicacion == TIMESTAMP
    assert location.timestamp_ubicacion.utcoffset().total_seconds() == 0


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-10-20T15:04:05",
        "2026-10-20T15:04:05-03:00",
    ],
)
def test_actualizar_ubicacion_rejects_non_utc_timestamp(timestamp: str) -> None:
    with pytest.raises(ValidationError):
        ActualizarUbicacion(
            conductor_id=CONDUCTOR_ID,
            latitud=0,
            longitud=0,
            timestamp_ubicacion=timestamp,
        )


def test_actualizar_ubicacion_rejects_malformed_timestamp() -> None:
    with pytest.raises(ValidationError):
        ActualizarUbicacion(
            conductor_id=CONDUCTOR_ID,
            latitud=0,
            longitud=0,
            timestamp_ubicacion="not-a-timestamp",
        )


@pytest.mark.parametrize(
    ("latitud", "longitud"),
    [
        (float("nan"), 0),
        (0, float("nan")),
        (float("inf"), 0),
        (0, float("-inf")),
    ],
)
def test_actualizar_ubicacion_rejects_non_finite_coordinates(
    latitud: float, longitud: float
) -> None:
    with pytest.raises(ValidationError):
        ActualizarUbicacion(
            conductor_id=CONDUCTOR_ID,
            latitud=latitud,
            longitud=longitud,
            timestamp_ubicacion=TIMESTAMP,
        )


def test_actualizar_ubicacion_rejects_additional_fields() -> None:
    with pytest.raises(ValidationError):
        ActualizarUbicacion(
            conductor_id=CONDUCTOR_ID,
            latitud=0,
            longitud=0,
            timestamp_ubicacion=TIMESTAMP,
            estado="ACTIVE",
        )


def test_ubicacion_registrada_accepts_valid_response() -> None:
    recorded = UbicacionRegistrada(
        conductor_id=CONDUCTOR_ID,
        timestamp_ubicacion=TIMESTAMP,
        recibida_en=TIMESTAMP,
        vigente=True,
        expira_en=datetime(2026, 10, 20, 15, 4, 35, tzinfo=timezone.utc),
    )

    assert recorded.vigente is True
    assert recorded.expira_en is not None


def test_ubicacion_registrada_rejects_false_vigente_and_extra_fields() -> None:
    valid_payload = {
        "conductor_id": CONDUCTOR_ID,
        "timestamp_ubicacion": TIMESTAMP,
        "recibida_en": TIMESTAMP,
        "vigente": True,
    }

    with pytest.raises(ValidationError):
        UbicacionRegistrada(**{**valid_payload, "vigente": False})

    with pytest.raises(ValidationError):
        UbicacionRegistrada(**{**valid_payload, "latitud": 0})


def test_ubicacion_registrada_rejects_non_utc_timestamps() -> None:
    with pytest.raises(ValidationError):
        UbicacionRegistrada(
            conductor_id=CONDUCTOR_ID,
            timestamp_ubicacion=TIMESTAMP,
            recibida_en=datetime(2026, 10, 20, 15, 4, 5),
            vigente=True,
        )
