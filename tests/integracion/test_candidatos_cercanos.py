from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.db.cache_config import cache
from app.esquemas.esquemas import Coordenada
from app.modelos.cache_models import (
    CacheEstOp,
    CacheResTemp,
    EstadoTmp as EstadoTmpCache,
    UbicacionesCond,
)


URL = "/api/v1/conductores/cercanos"
PARAMETROS = {
    "origen_latitud": -27.451,
    "origen_longitud": -58.986,
    "tipo_vehiculo": "AUTO",
}


def assert_problema(respuesta, status, codigo=None):
    assert respuesta.status_code == status
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert respuesta.headers["x-request-id"]
    problema = respuesta.json()
    assert {"type", "title", "status", "detail", "instance"} <= problema.keys()
    assert problema["status"] == status
    assert problema["instance"] == URL
    assert problema.get("trace_id") == respuesta.headers["x-request-id"]
    if codigo:
        assert problema["code"] == codigo
    return problema


def test_sin_token_responde_401_problem_details(cliente_sin_token, validar_jwt_real):
    respuesta = cliente_sin_token.get(URL, params=PARAMETROS)

    assert_problema(respuesta, 401, "NO_AUTENTICADO")


def test_token_sin_roles_responde_403_problem_details(cliente_test):
    respuesta = cliente_test.get(
        URL,
        params=PARAMETROS,
        headers={"Authorization": "Bearer integration-no-roles-token"},
    )

    assert_problema(respuesta, 403, "SIN_PERMISO")


@pytest.mark.parametrize(
    "parametros",
    [
        {**PARAMETROS, "origen_latitud": 91},
        {**PARAMETROS, "tipo_vehiculo": "CAMION"},
        {"origen_latitud": -27.451, "tipo_vehiculo": "AUTO"},
    ],
)
def test_parametros_invalidos_responden_422_problem_details(
    cliente_test, parametros
):
    respuesta = cliente_test.get(URL, params=parametros)

    problema = assert_problema(respuesta, 422)
    assert problema["invalid_params"]


def test_busqueda_persiste_consulta_y_respeta_contrato(cliente_test):
    from app.servicios import candidatosCercanos

    conductor_sin_reserva = uuid4()
    conductor_liberado = uuid4()
    conductor_reservado = uuid4()
    conductores = [
        conductor_sin_reserva,
        conductor_liberado,
        conductor_reservado,
    ]
    ahora = datetime.now(timezone.utc)
    solicitud_liberada = uuid4()
    solicitud_reservada = uuid4()
    clave_rate_limit = "rl:buscar_conductores_cercanos:jwt:integration-tests"

    try:
        for index, conductor_id in enumerate(conductores):
            ubicacion = UbicacionesCond(
                pk=str(conductor_id),
                conductor_id=conductor_id,
                geo=Coordenada(
                    latitud=PARAMETROS["origen_latitud"] + (index + 1) * 0.001,
                    longitud=PARAMETROS["origen_longitud"],
                ),
                timestamp_ubicacion=ahora,
            )
            ubicacion.save()
            ubicacion.expire(30)

            estado = CacheEstOp(
                pk=str(conductor_id),
                conductor_id=conductor_id,
                connected=True,
                available=True,
                timestamp_evento=ahora,
            )
            estado.save()

        for conductor_id, solicitud_id, estado_temporal in (
            (conductor_liberado, solicitud_liberada, EstadoTmpCache.LIBERADO),
            (conductor_reservado, solicitud_reservada, EstadoTmpCache.RESERVADO),
        ):
            reserva = CacheResTemp(
                pk=str(conductor_id),
                conductor_id=conductor_id,
                solicitud_id=solicitud_id,
                estado_temporal=estado_temporal,
                actualizado_en=ahora,
                expira_en=ahora + timedelta(minutes=10),
            )
            reserva.save()
            reserva.expire(600)

        respuestas_m3 = []
        for conductor_id in (conductor_sin_reserva, conductor_liberado):
            respuestas_m3.extend(
                [
                    Mock(
                        status_code=200,
                        text="",
                        json=Mock(
                            return_value={
                                "estado": "DISPONIBLE",
                                "id_vehiculo_activo": f"vehiculo-{conductor_id}",
                            }
                        ),
                    ),
                    Mock(
                        status_code=200,
                        text="",
                        json=Mock(
                            return_value={
                                "tipo": "AUTO",
                                "habilitacion": "APROBADA",
                            }
                        ),
                    ),
                ]
            )
        cliente_m3 = MagicMock()
        cliente_m3.get.side_effect = respuestas_m3

        with (
            patch.object(
                candidatosCercanos,
                "_TOKEN_CACHE",
                {"token": "token-prueba", "expira_en": float("inf")},
            ),
            patch.object(candidatosCercanos.httpx, "Client") as cliente_http,
        ):
            cliente_http.return_value.__enter__.return_value = cliente_m3
            respuesta = cliente_test.get(URL, params=PARAMETROS)

        assert respuesta.status_code == 200
        assert respuesta.headers["x-request-id"]
        assert respuesta.headers["cache-control"] == "no-store"
        cuerpo = respuesta.json()
        assert set(cuerpo) == {"conductores", "radio_aplicado_km", "generado_en"}
        assert cuerpo["radio_aplicado_km"] == 5.0
        candidatos = cuerpo["conductores"]
        assert len(candidatos) == 2
        assert {c["conductor_id"] for c in candidatos} == {
            str(conductor_sin_reserva),
            str(conductor_liberado),
        }
        assert all(
            set(candidato)
            == {
                "conductor_id",
                "distancia_origen_km",
                "eta_retiro_minutos",
                "tipo_vehiculo",
            }
            for candidato in candidatos
        )
        assert [c["distancia_origen_km"] for c in candidatos] == sorted(
            c["distancia_origen_km"] for c in candidatos
        )
        assert all(c["tipo_vehiculo"] == "AUTO" for c in candidatos)
        assert all(c["eta_retiro_minutos"] >= 1 for c in candidatos)
        datetime.fromisoformat(cuerpo["generado_en"].replace("Z", "+00:00"))
        assert cliente_m3.get.call_count == 4
    finally:
        for conductor_id in conductores:
            UbicacionesCond.delete(str(conductor_id))
            CacheEstOp.delete(str(conductor_id))
            CacheResTemp.delete(str(conductor_id))
        cache.delete(clave_rate_limit)
