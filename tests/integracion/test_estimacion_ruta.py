from datetime import timezone

import pytest
from fastapi.testclient import TestClient

from app.esquemas.esquemas import (
    ConsultaEstimacionRuta,
    FuenteInfo,
    VehiculosSoportados,
)
from app.servicios.calculosDeEstimacion import CalculosDeViaje
from app.main import app


client = TestClient(app)


def crear_consulta(tipo_vehiculo=VehiculosSoportados.AUTO):
    return ConsultaEstimacionRuta(
        origen_latitud=0.0,
        origen_longitud=0.0,
        destino_latitud=0.0,
        destino_longitud=1.0,
        tipo_vehiculo=tipo_vehiculo,
    )


def test_estimacion_devuelve_distancia_eta_fuente_y_fecha_utc():
    resultado = CalculosDeViaje(crear_consulta())

    assert resultado.distancia_estimada_km == pytest.approx(144.72, abs=0.01)
    assert resultado.eta_minutos == 290
    assert resultado.fuente == FuenteInfo.ESTIMACION_LOCAL
    assert resultado.calculado_en.tzinfo == timezone.utc
    assert resultado.model_dump().keys() == {
        "distancia_estimada_km",
        "eta_minutos",
        "calculado_en",
        "fuente",
    }


def test_moto_estima_eta_menor_y_auto_es_el_tipo_predeterminado():
    consulta_predeterminada = crear_consulta()
    consulta_moto = crear_consulta(VehiculosSoportados.MOTO)

    resultado_auto = CalculosDeViaje(consulta_predeterminada)
    resultado_moto = CalculosDeViaje(consulta_moto)

    assert consulta_predeterminada.tipo_vehiculo == VehiculosSoportados.AUTO
    assert resultado_auto.eta_minutos == 290
    assert resultado_moto.eta_minutos == 249
    assert resultado_moto.eta_minutos < resultado_auto.eta_minutos


def test_endpoint_estimacion_devuelve_contrato_y_request_id():
    respuesta = client.get(
        "/api/v1/rutas/estimacion",
        params={
            "origen_latitud": 0.0,
            "origen_longitud": 0.0,
            "destino_latitud": 0.0,
            "destino_longitud": 1.0,
            "tipo_vehiculo": "AUTO",
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["fuente"] == "estimacion_local"
    assert respuesta.json()["distancia_estimada_km"] == pytest.approx(
        144.72, abs=0.01
    )
    assert respuesta.json()["eta_minutos"] == 290
    assert respuesta.headers["x-request-id"]


def test_endpoint_rechaza_coordenadas_fuera_de_rango():
    respuesta = client.get(
        "/api/v1/rutas/estimacion",
        params={
            "origen_latitud": 91,
            "origen_longitud": 0,
            "destino_latitud": 0,
            "destino_longitud": 1,
        },
    )

    assert respuesta.status_code == 422
