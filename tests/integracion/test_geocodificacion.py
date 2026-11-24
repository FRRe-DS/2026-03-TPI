from unittest.mock import patch
from app.esquemas.esquemas import ConsultaGeocodificacion

# Simulamos el resolver para no pegarle a Geopy ni depender del JSON local
@patch("app.servicios.cadenaDeProveedores.AdaptadorEncadenado.resolver")
def test_geocodificacion_exitosa_200(mock_resolver, cliente_test):
    # Definimos qué devolverá el mock cuando el router lo llame
    mock_resolver.return_value = {
        "coincidencias": [
            {
                "latitud": -27.451,
                "longitud": -58.986,
                "etiqueta": "UTN FRRe, Resistencia",
                "confianza": 1.0
            }
        ]
    }

    body = {
        "direccion": "French 414",
        "localidad": "Resistencia",
        "pais": "ar"
    }

    response = cliente_test.post("/api/v1/geocodificaciones", json=body)
    
    assert response.status_code == 200
    datos = response.json()
    assert "coincidencias" in datos
    assert len(datos["coincidencias"]) == 1
    assert datos["coincidencias"][0]["etiqueta"] == "UTN FRRe, Resistencia"
    assert response.headers["x-request-id"]
    mock_resolver.assert_called_once()

def test_geocodificacion_falla_validacion_422(cliente_test):
    # Enviamos un país inválido (3 letras en lugar de 2) para disparar la excepción de Pydantic
    body = {
        "direccion": "French 414",
        "localidad": "Resistencia",
        "pais": "arg" # El esquema exige max_length=2
    }

    response = cliente_test.post("/api/v1/geocodificaciones", json=body)
    
    assert response.status_code == 422
    problema = response.json()
    assert problema["status"] == 422
    assert problema["invalid_params"]
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["x-request-id"]