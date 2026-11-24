from fastapi import Request
from fastapi.testclient import TestClient

import pytest

from app.errores.exceptionsSemanticos import NoAutenticado
from app.main import app
from app.seguridad.authManager import validar_token_keycloak

TOKEN_VALIDO = "integration-valid-token"
TOKEN_SIN_ROLES = "integration-no-roles-token"
ROLES_TEST = [
    "conductores-be",
    "ubicacion-be",
    "solicitud-be",
    "tarifas-be",
    "reservas-be",
]


def mock_validar_token_keycloak(request: Request) -> dict:
    authorization = request.headers.get("authorization", "")
    esquema, separador, token = authorization.partition(" ")
    if esquema.lower() != "bearer" or not separador or not token:
        raise NoAutenticado(detail="Falta token de acceso Bearer.")

    if token == TOKEN_VALIDO:
        roles = ROLES_TEST
    elif token == TOKEN_SIN_ROLES:
        roles = []
    else:
        raise NoAutenticado(detail="Certificado de acceso inválido o corrupto.")

    return {
        "realm_access": {"roles": roles},
        "sub": "018f1f20-7b4a-7cc2-9d41-66382a18cc5a",
        "azp": "integration-tests",
    }


@pytest.fixture(autouse=True)
def mock_keycloak():
    overrides_anteriores = app.dependency_overrides.copy()
    app.dependency_overrides[validar_token_keycloak] = mock_validar_token_keycloak
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(overrides_anteriores)


@pytest.fixture
def cliente_test(mock_keycloak):
    with TestClient(
        app,
        headers={"Authorization": f"Bearer {TOKEN_VALIDO}"},
    ) as cliente:
        yield cliente


@pytest.fixture
def cliente_sin_token(mock_keycloak):
    with TestClient(app) as cliente:
        yield cliente


@pytest.fixture
def validar_jwt_real(mock_keycloak):
    override = app.dependency_overrides.pop(validar_token_keycloak)
    yield
    app.dependency_overrides[validar_token_keycloak] = override
