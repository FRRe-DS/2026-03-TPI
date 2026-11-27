from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID

import httpx
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.esquemas.esquemas import EstadoTmp, QueryCercanos, VehiculosSoportados


TRACE_ID = "test-candidatos-cercanos"
CONDUCTOR_1 = UUID("00000000-0000-0000-0000-000000000001")
CONDUCTOR_2 = UUID("00000000-0000-0000-0000-000000000002")
CONDUCTOR_3 = UUID("00000000-0000-0000-0000-000000000003")


@pytest.fixture
def servicio(cargar_aislado):
    modulo = cargar_aislado("app.servicios.candidatosCercanos")
    modulo._TOKEN_CACHE.update(token=None, expira_en=0.0)
    yield modulo


def respuesta(status_code, payload=None):
    resp = Mock(status_code=status_code, text="respuesta M3")
    resp.json.return_value = payload or {}
    return resp


def ubicacion(conductor_id, latitud):
    return SimpleNamespace(
        conductor_id=conductor_id,
        geo=SimpleNamespace(latitud=latitud, longitud=0.0),
    )


def preparar_busqueda(servicio, ubicaciones, estados=None, reservas=None):
    ubicaciones_por_id = {
        str(ubicacion.conductor_id): ubicacion for ubicacion in ubicaciones
    }
    servicio.UbicacionesCond.all_pks.return_value = list(ubicaciones_por_id)
    servicio.UbicacionesCond.get.side_effect = ubicaciones_por_id.__getitem__

    estados = estados or {}

    def obtener_estado(conductor_id):
        resultado = estados.get(conductor_id)
        if resultado is servicio.NotFoundError:
            raise servicio.NotFoundError
        if isinstance(resultado, BaseException):
            raise resultado
        return resultado

    servicio.CacheEstOp.get.side_effect = obtener_estado

    reservas = reservas or {}

    def obtener_reserva(conductor_id):
        resultado = reservas.get(conductor_id, servicio.NotFoundError)
        if resultado is servicio.NotFoundError:
            raise servicio.NotFoundError
        if isinstance(resultado, BaseException):
            raise resultado
        return resultado

    servicio.CacheResTemp.get.side_effect = obtener_reserva


def ejecutar_busqueda(servicio, query, verificacion=True):
    cliente = MagicMock()
    with (
        patch.object(
            servicio, "_construir_headers_m3", return_value={"Authorization": "Bearer test"}
        ),
        patch.object(servicio.httpx, "Client") as cliente_http,
        patch.object(
            servicio, "_verificar_candidato_m3", return_value=verificacion
        ) as verificar,
    ):
        cliente_http.return_value.__enter__.return_value = cliente
        resultado = servicio.CandidatosCercanos.buscar(query, TRACE_ID)
    return resultado, cliente_http, verificar


def test_token_estatico_y_headers_no_consultan_keycloak(servicio):
    servicio.M3_SERVICE_TOKEN = "token-estatico"
    servicio._TOKEN_CACHE.update(
        token=servicio.M3_SERVICE_TOKEN,
        expira_en=float("inf"),
    )
    with patch.object(servicio.httpx, "post") as post:
        assert servicio._obtener_token_m3() == "token-estatico"
        assert servicio._construir_headers_m3() == {
            "Accept": "application/json",
            "Authorization": "Bearer token-estatico",
        }
    post.assert_not_called()


def test_obtener_token_client_credentials_cachea_respuesta(servicio):
    servicio.M3_CLIENT_ID_ACTUAL = "cliente-m3"
    servicio.M3_SECRET_CLIENT_ACTUAL = "secreto-m3"
    servicio.KEYCLOAK_TOKEN_URL = "https://keycloak/token"
    token_response = Mock()
    token_response.json.return_value = {
        "access_token": "token-nuevo",
        "expires_in": 60,
    }

    with (
        patch.object(servicio.time, "time", return_value=100.0),
        patch.object(servicio.httpx, "post", return_value=token_response) as post,
    ):
        assert servicio._obtener_token_m3() == "token-nuevo"
        assert servicio._obtener_token_m3() == "token-nuevo"

    post.assert_called_once_with(
        "https://keycloak/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "cliente-m3",
            "client_secret": "secreto-m3",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=servicio.M3_TIMEOUT_SECONDS,
    )
    assert servicio._TOKEN_CACHE == {
        "token": "token-nuevo",
        "expira_en": 160.0,
    }


def test_obtener_token_renueva_si_quedan_menos_de_15_segundos(servicio):
    servicio.M3_CLIENT_ID_ACTUAL = "cliente-m3"
    servicio.M3_SECRET_CLIENT_ACTUAL = "secreto-m3"
    servicio._TOKEN_CACHE.update(token="token-por-vencer", expira_en=114.0)
    token_response = Mock()
    token_response.json.return_value = {"access_token": "token-renovado"}

    with (
        patch.object(servicio.time, "time", return_value=100.0),
        patch.object(servicio.httpx, "post", return_value=token_response) as post,
    ):
        assert servicio._obtener_token_m3() == "token-renovado"

    post.assert_called_once()


def test_obtener_token_falla_si_no_hay_credenciales_ni_token(servicio):
    servicio.M3_CLIENT_ID_ACTUAL = ""
    servicio.M3_SECRET_CLIENT_ACTUAL = ""
    servicio.M3_SERVICE_TOKEN = ""
    servicio._TOKEN_CACHE.update(token=None, expira_en=0.0)

    with pytest.raises(RuntimeError, match="Faltan M3_KEYCLOAK_CLIENT_ID"):
        servicio._obtener_token_m3()


def test_verificar_candidato_m3_valido(servicio):
    client = Mock()
    client.get.side_effect = [
        respuesta(
            200,
            {"estado": "DISPONIBLE", "id_vehiculo_activo": "vehiculo-1"},
        ),
        respuesta(
            200,
            {"tipo": "AUTO", "habilitacion": "APROBADA"},
        ),
    ]

    assert servicio._verificar_candidato_m3(
        client, CONDUCTOR_1, VehiculosSoportados.AUTO, TRACE_ID
    )
    assert [call.args[0] for call in client.get.call_args_list] == [
        f"/conductores/{CONDUCTOR_1}/estado",
        f"/conductores/{CONDUCTOR_1}/vehiculos/vehiculo-1",
    ]


@pytest.mark.parametrize(
    "etapa,status_code",
    [("estado", 404), ("estado", 503), ("vehiculo", 404), ("vehiculo", 503)],
)
def test_verificar_candidato_descarta_respuestas_http_no_exitosas(
    servicio, etapa, status_code
):
    client = Mock()
    respuestas = [respuesta(200, {"estado": "DISPONIBLE", "id_vehiculo_activo": "v1"})]
    if etapa == "estado":
        respuestas = [respuesta(status_code)]
    else:
        respuestas.append(respuesta(status_code))
    client.get.side_effect = respuestas

    assert not servicio._verificar_candidato_m3(
        client, CONDUCTOR_1, VehiculosSoportados.AUTO, TRACE_ID
    )
    assert client.get.call_count == len(respuestas)


@pytest.mark.parametrize(
    "estado",
    [
        {"estado": "OCUPADO", "id_vehiculo_activo": "v1"},
        {"estado": "DISPONIBLE", "id_vehiculo_activo": None},
    ],
)
def test_verificar_candidato_descarta_estado_no_disponible_o_sin_vehiculo(
    servicio, estado
):
    client = Mock()
    client.get.return_value = respuesta(200, estado)

    assert not servicio._verificar_candidato_m3(
        client, CONDUCTOR_1, VehiculosSoportados.AUTO, TRACE_ID
    )
    client.get.assert_called_once_with(f"/conductores/{CONDUCTOR_1}/estado")


@pytest.mark.parametrize(
    "vehiculo",
    [
        {"tipo": "MOTO", "habilitacion": "APROBADA"},
        {"tipo": "AUTO", "habilitacion": "PENDIENTE"},
    ],
)
def test_verificar_candidato_descarta_vehiculo_incompatible_o_no_aprobado(
    servicio, vehiculo
):
    client = Mock()
    client.get.side_effect = [
        respuesta(200, {"estado": "DISPONIBLE", "id_vehiculo_activo": "v1"}),
        respuesta(200, vehiculo),
    ]

    assert not servicio._verificar_candidato_m3(
        client, CONDUCTOR_1, VehiculosSoportados.AUTO, TRACE_ID
    )


@pytest.mark.parametrize(
    "etapa,error",
    [
        ("estado", httpx.TimeoutException("timeout")),
        ("estado", httpx.ConnectError("fallo HTTP")),
        ("estado", RuntimeError("fallo inesperado")),
        ("vehiculo", httpx.TimeoutException("timeout")),
        ("vehiculo", httpx.ConnectError("fallo HTTP")),
        ("vehiculo", RuntimeError("fallo inesperado")),
    ],
)
def test_verificar_candidato_es_resiliente_a_excepciones(servicio, etapa, error):
    client = Mock()
    estado_ok = respuesta(
        200, {"estado": "DISPONIBLE", "id_vehiculo_activo": "v1"}
    )
    client.get.side_effect = (
        [error] if etapa == "estado" else [estado_ok, error]
    )

    assert not servicio._verificar_candidato_m3(
        client, CONDUCTOR_1, VehiculosSoportados.AUTO, TRACE_ID
    )


def test_buscar_expande_a_6_5_km_y_se_detiene_en_el_primer_radio_valido(servicio):
    preparar_busqueda(
        servicio,
        [ubicacion(CONDUCTOR_1, 0.058)],
        {str(CONDUCTOR_1): Mock(connected=True, available=True)},
    )

    resultado, cliente_http, verificar = ejecutar_busqueda(
        servicio,
        QueryCercanos(
            origen_latitud=0.0,
            origen_longitud=0.0,
            tipo_vehiculo=VehiculosSoportados.AUTO,
        ),
    )

    assert resultado.radio_aplicado_km == 6.5
    assert [c.conductor_id for c in resultado.conductores] == [CONDUCTOR_1]
    cliente_http.assert_called_once()
    verificar.assert_called_once()


def test_buscar_ordena_calcula_eta_y_aplica_limite(servicio):
    ids = [CONDUCTOR_1, CONDUCTOR_2, CONDUCTOR_3]
    preparar_busqueda(
        servicio,
        [ubicacion(ids[0], 0.018), ubicacion(ids[1], 0.004), ubicacion(ids[2], 0.009)],
        {
            str(conductor_id): Mock(connected=True, available=True)
            for conductor_id in ids
        },
    )

    resultado, _, verificar = ejecutar_busqueda(
        servicio,
        QueryCercanos(
            origen_latitud=0.0,
            origen_longitud=0.0,
            tipo_vehiculo=VehiculosSoportados.AUTO,
            limite=2,
        ),
    )

    assert resultado.radio_aplicado_km == 5.0
    assert [c.conductor_id for c in resultado.conductores] == [CONDUCTOR_2, CONDUCTOR_3]
    assert [c.distancia_origen_km for c in resultado.conductores] == sorted(
        c.distancia_origen_km for c in resultado.conductores
    )
    for candidato in resultado.conductores:
        assert candidato.eta_retiro_minutos == max(
            1, round(candidato.distancia_origen_km * 3)
        )
    assert [item.kwargs["conductor_id"] for item in verificar.call_args_list] == ids
    assert all(
        item.kwargs["tipo_vehiculo_requerido"] is VehiculosSoportados.AUTO
        and item.kwargs["trace_id"] == TRACE_ID
        for item in verificar.call_args_list
    )


@pytest.mark.parametrize(
    "estado_op",
    [
        (False, True),
        (True, False),
        NotImplemented,
    ],
)
def test_buscar_descarta_estado_operativo_invalido_o_ausente(servicio, estado_op):
    estado = (
        servicio.NotFoundError
        if estado_op is NotImplemented
        else Mock(connected=estado_op[0], available=estado_op[1])
    )
    preparar_busqueda(
        servicio,
        [ubicacion(CONDUCTOR_1, 0.001)],
        {str(CONDUCTOR_1): estado},
    )

    _, _, verificar = ejecutar_busqueda(
        servicio,
        QueryCercanos(
            origen_latitud=0.0,
            origen_longitud=0.0,
            tipo_vehiculo=VehiculosSoportados.AUTO,
        ),
    )

    verificar.assert_not_called()
    servicio.CacheResTemp.get.assert_not_called()


def test_buscar_descarta_candidato_si_redis_no_disponible_en_cache_operativa(servicio):
    preparar_busqueda(
        servicio,
        [ubicacion(CONDUCTOR_1, 0.001)],
        {str(CONDUCTOR_1): RedisConnectionError("redis caido")},
    )

    _, _, verificar = ejecutar_busqueda(
        servicio,
        QueryCercanos(
            origen_latitud=0.0,
            origen_longitud=0.0,
            tipo_vehiculo=VehiculosSoportados.AUTO,
        ),
    )

    verificar.assert_not_called()
    servicio.CacheResTemp.get.assert_not_called()


def test_buscar_omite_ubicacion_expirada_y_procesa_los_demas_conductores(servicio):
    preparar_busqueda(
        servicio,
        [
            ubicacion(CONDUCTOR_1, 0.001),
            ubicacion(CONDUCTOR_2, 0.002),
        ],
        {str(CONDUCTOR_2): Mock(connected=True, available=True)},
    )
    servicio.UbicacionesCond.get.side_effect = [
        servicio.NotFoundError,
        ubicacion(CONDUCTOR_2, 0.002),
    ]

    resultado, _, verificar = ejecutar_busqueda(
        servicio,
        QueryCercanos(
            origen_latitud=0.0,
            origen_longitud=0.0,
            tipo_vehiculo=VehiculosSoportados.AUTO,
        ),
    )

    assert [c.conductor_id for c in resultado.conductores] == [CONDUCTOR_2]
    assert [call.args[0] for call in servicio.UbicacionesCond.get.call_args_list] == [
        str(CONDUCTOR_1),
        str(CONDUCTOR_2),
    ]
    verificar.assert_called_once()


def test_buscar_falla_con_dependencia_no_disponible_si_redis_falla_al_leer_ubicacion(
    servicio,
):
    servicio.UbicacionesCond.all_pks.return_value = [str(CONDUCTOR_1)]
    servicio.UbicacionesCond.get.side_effect = RedisConnectionError("redis caido")

    with pytest.raises(servicio.DependenciaNoDisponible):
        ejecutar_busqueda(
            servicio,
            QueryCercanos(
                origen_latitud=0.0,
                origen_longitud=0.0,
                tipo_vehiculo=VehiculosSoportados.AUTO,
            ),
        )


def test_buscar_filtra_reservado_y_admite_liberado_o_sin_reserva(servicio):
    preparar_busqueda(
        servicio,
        [
            ubicacion(CONDUCTOR_1, 0.001),
            ubicacion(CONDUCTOR_2, 0.002),
            ubicacion(CONDUCTOR_3, 0.003),
        ],
        {
            str(conductor_id): Mock(connected=True, available=True)
            for conductor_id in (CONDUCTOR_1, CONDUCTOR_2, CONDUCTOR_3)
        },
        {
            str(CONDUCTOR_1): Mock(estado_temporal=EstadoTmp.RESERVADO),
            str(CONDUCTOR_2): Mock(estado_temporal=EstadoTmp.LIBERADO),
        },
    )

    resultado, _, verificar = ejecutar_busqueda(
        servicio,
        QueryCercanos(
            origen_latitud=0.0,
            origen_longitud=0.0,
            tipo_vehiculo=VehiculosSoportados.AUTO,
        ),
    )

    assert {c.conductor_id for c in resultado.conductores} == {
        CONDUCTOR_2,
        CONDUCTOR_3,
    }
    assert verificar.call_count == 2


def test_buscar_agota_radios_progresivos_y_devuelve_vacio_en_9_5(servicio):
    preparar_busqueda(
        servicio,
        [ubicacion(CONDUCTOR_1, 0.001)],
        {str(CONDUCTOR_1): Mock(connected=True, available=True)},
    )

    resultado, _, verificar = ejecutar_busqueda(
        servicio,
        QueryCercanos(
            origen_latitud=0.0,
            origen_longitud=0.0,
            tipo_vehiculo=VehiculosSoportados.AUTO,
        ),
        verificacion=False,
    )

    assert resultado.conductores == []
    assert resultado.radio_aplicado_km == 9.5
    assert verificar.call_count == 4
