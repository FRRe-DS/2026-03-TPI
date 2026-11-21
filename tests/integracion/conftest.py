import sys
import os

import pytest
from fastapi.testclient import TestClient
# 2. Ahora sí importamos la app (no fallará porque la variable ya existe en memoria)
from app.main import app
from app.seguridad.authManager import validar_token_keycloak

# Simulamos la respuesta exitosa de Keycloak
def mock_validar_token_keycloak():
    return {
        "realm_access": {"roles": ["rol_permitido"]},
        "sub": "018f1f20-7b4a-7cc2-9d41-66382a18cc5a" # ID simulado
    }

# Reemplazamos la dependencia real por el mock antes de correr los tests
app.dependency_overrides[validar_token_keycloak] = mock_validar_token_keycloak

@pytest.fixture
def cliente_test():
    """Fixture que provee el cliente HTTP de prueba para todos los tests."""
    return TestClient(app)