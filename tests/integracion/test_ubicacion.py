import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from redis_om.model import NotFoundError

# Generamos un ID de conductor válido para la URL
CONDUCTOR_ID = str(uuid4())
URL_UBICACION = f"/api/v1/conductores/{CONDUCTOR_ID}/ubicacion"

@patch("app.servicios.actualizarUbicacion.UbicacionesCond.get")
@patch("app.servicios.actualizarUbicacion.UbicacionesCond.save")
@patch("app.servicios.actualizarUbicacion.UbicacionesCond.expire")
def test_ubicacion_creacion_nueva_201(mock_expire, mock_save, mock_get, cliente_test):
    # Forzamos NotFoundError para simular que el conductor no está en Redis
    mock_get.side_effect = NotFoundError()
    
    body = {
        "latitud": -27.451,
        "longitud": -58.986,
        "timestamp_ubicacion": datetime.now(timezone.utc).isoformat()
    }

    response = cliente_test.put(URL_UBICACION, json=body)
    
    # El servicio debe retornar True (es_nuevo) y el router responder 201 Created
    assert response.status_code == 201
    datos = response.json()
    assert datos["vigente"] is True
    assert datos["conductor_id"] == CONDUCTOR_ID

@patch("app.servicios.actualizarUbicacion.UbicacionesCond.get")
@patch("app.servicios.actualizarUbicacion.UbicacionesCond.save")
def test_ubicacion_actualizacion_200(mock_save, mock_get, cliente_test):
    # Simulamos un objeto existente en Redis con un timestamp de hace 5 minutos
    mock_ubicacion_existente = MagicMock()
    mock_ubicacion_existente.timestamp_ubicacion = datetime.now(timezone.utc) - timedelta(minutes=5)
    mock_get.return_value = mock_ubicacion_existente
    
    # Enviamos un timestamp actual, lo que representa una actualización válida
    body = {
        "latitud": -27.455,
        "longitud": -58.990,
        "timestamp_ubicacion": datetime.now(timezone.utc).isoformat()
    }

    response = cliente_test.put(URL_UBICACION, json=body)
    
    # El servicio debe retornar False (es_nuevo) y el router responder 200 OK
    assert response.status_code == 200
    mock_ubicacion_existente.save.assert_called_once_with()

@patch("app.servicios.actualizarUbicacion.UbicacionesCond.get")
def test_ubicacion_rechazo_timestamp_antiguo_409(mock_get, cliente_test):
    # Simulamos que la caché tiene un registro muy reciente
    mock_ubicacion_existente = MagicMock()
    mock_ubicacion_existente.timestamp_ubicacion = datetime.now(timezone.utc)
    mock_get.return_value = mock_ubicacion_existente
    
    # Intentamos enviar un timestamp de hace 10 minutos
    timestamp_viejo = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    body = {
        "latitud": -27.455,
        "longitud": -58.990,
        "timestamp_ubicacion": timestamp_viejo
    }

    response = cliente_test.put(URL_UBICACION, json=body)
    
    # La regla de negocio debe levantar ErrorTimeStamp y el router mapearlo a 409
    assert response.status_code == 409
