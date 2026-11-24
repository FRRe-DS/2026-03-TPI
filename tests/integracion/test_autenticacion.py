import jwt

from app.seguridad import authManager


PARAMETROS_ESTIMACION = {
    "origen_latitud": 0,
    "origen_longitud": 0,
    "destino_latitud": 0,
    "destino_longitud": 1,
}


def assert_problema(respuesta, status):
    assert respuesta.status_code == status
    assert respuesta.headers["content-type"] == "application/problem+json"
    assert respuesta.headers["x-request-id"]
    assert respuesta.json()["status"] == status


def test_sin_token_responde_401(cliente_sin_token, validar_jwt_real):
    respuesta = cliente_sin_token.get(
        "/api/v1/rutas/estimacion",
        params=PARAMETROS_ESTIMACION,
    )

    assert_problema(respuesta, 401)
    assert respuesta.json()["code"] == "NO_AUTENTICADO"


def test_token_jwt_invalido_responde_401_sin_contactar_keycloak(
    cliente_sin_token, validar_jwt_real
):
    from unittest.mock import patch

    with patch.object(
        authManager.token_publico,
        "get_signing_key_from_jwt",
        side_effect=jwt.InvalidTokenError("firma inválida"),
    ):
        respuesta = cliente_sin_token.get(
            "/api/v1/rutas/estimacion",
            params=PARAMETROS_ESTIMACION,
            headers={"Authorization": "Bearer token-invalido"},
        )

    assert_problema(respuesta, 401)
    assert respuesta.json()["code"] == "NO_AUTENTICADO"


def test_token_valido_sin_rol_requerido_responde_403(cliente_test):
    respuesta = cliente_test.get(
        "/api/v1/rutas/estimacion",
        params=PARAMETROS_ESTIMACION,
        headers={"Authorization": "Bearer integration-no-roles-token"},
    )

    assert_problema(respuesta, 403)
    assert respuesta.json()["code"] == "SIN_PERMISO"


def test_readiness_verifica_postgres_y_redis_sin_autenticacion(cliente_sin_token):
    respuesta = cliente_sin_token.get("/health/ready")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "READY"}
    assert respuesta.headers["x-request-id"]
