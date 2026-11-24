from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.esquemas.esquemas import QueryEstimacionRuta, ResultadoEstimacionRuta
from app.servicios.calculosDeEstimacion import CalculosDeViaje


@pytest.mark.parametrize('vehiculo', ['AUTO', 'MOTO'])
@pytest.mark.parametrize('destino', [(0, 0), (0, 1)])
def test_distancia_eta_y_origen_identico(vehiculo, destino):
    datos = QueryEstimacionRuta(origen_latitud=0, origen_longitud=0,
        destino_latitud=destino[0], destino_longitud=destino[1], tipo_vehiculo=vehiculo)
    distancia_linea_recta = 0 if destino == (0, 0) else 111.31949079327356
    with patch('app.servicios.calculosDeEstimacion.geodesic',
        return_value=SimpleNamespace(kilometers=distancia_linea_recta)) as geodesica:
        resultado = CalculosDeViaje(datos, trace_id='unit-test')
    assert isinstance(resultado, ResultadoEstimacionRuta)
    assert resultado.distancia_estimada_km == pytest.approx(round(distancia_linea_recta * 1.3, 2))
    if destino == (0, 0):
        assert resultado.eta_minutos == 0
    else:
        assert resultado.eta_minutos > 0
    assert resultado.fuente == 'estimacion_local'
    geodesica.assert_called_once_with((0, 0), destino)


def test_tipo_vehiculo_opcional_y_distancia_cero():
    datos = QueryEstimacionRuta(
        origen_latitud=0,
        origen_longitud=0,
        destino_latitud=0,
        destino_longitud=0,
    )
    with patch('app.servicios.calculosDeEstimacion.geodesic',
        return_value=SimpleNamespace(kilometers=0)):
        resultado = CalculosDeViaje(datos, trace_id='unit-test')
    assert resultado.distancia_estimada_km == 0
    assert resultado.eta_minutos == 0
