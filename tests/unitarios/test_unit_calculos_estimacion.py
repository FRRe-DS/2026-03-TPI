"""Contratos pendientes: el servicio todavía contiene únicamente pass.

No se inventan velocidades: el proyecto no define factores para AUTO/MOTO.
Al implementar el servicio, estos xfail estrictos obligan a revisar las pruebas.
"""
from unittest.mock import Mock, patch

import pytest

from app.esquemas.esquemas import ConsultaEstimacionRuta, ResultadoEstimacionRuta
from app.servicios.calculosDeEstimacion import CalculosDeViaje


@pytest.mark.parametrize('vehiculo', ['AUTO', 'MOTO'])
@pytest.mark.parametrize('destino', [(0, 0), (0, 1)])
@pytest.mark.xfail(strict=True, raises=AssertionError,
    reason='CalculosDeViaje es pass; faltan implementación y velocidades por vehículo')
def test_distancia_eta_y_origen_identico(vehiculo, destino):
    datos = ConsultaEstimacionRuta(origen_latitud=0, origen_longitud=0,
        destino_latitud=destino[0], destino_longitud=destino[1], tipo_vehiculo=vehiculo)
    km = 0 if destino == (0, 0) else 111.31949079327356
    with patch('geopy.distance.geodesic', return_value=Mock(km=km)) as geodesica:
        resultado = CalculosDeViaje(datos)
        assert isinstance(resultado, ResultadoEstimacionRuta)
        assert resultado.distancia_estimada_km == pytest.approx(km, abs=0.01)
        if km == 0:
            assert resultado.eta_minutos == 0
        else:
            assert resultado.eta_minutos > 0
        geodesica.assert_called_once_with((0, 0), destino)
