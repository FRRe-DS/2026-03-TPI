from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from app.esquemas.esquemas import ActualizarUbicacion, Coordenada
from app.errores.exceptionsSemanticos import ErrorTimeStamp

ID = UUID('00000000-0000-0000-0000-000000000001')
AHORA = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def servicio(cargar_aislado):
    modulo = cargar_aislado('app.servicios.actualizarUbicacion')
    with patch.object(modulo, 'datetime') as reloj:
        reloj.now.return_value = AHORA
        reloj.utcnow.return_value = AHORA.replace(tzinfo=None)
        yield modulo


@pytest.mark.parametrize('nuevo', [True, False])
@pytest.mark.parametrize('error_ttl', [False, True])
def test_crear_actualizar_y_ttl(servicio, nuevo, error_ttl):
    repo = servicio.UbicacionesCond
    existente = Mock(timestamp_ubicacion=AHORA - timedelta(seconds=1))
    repo.get.return_value = existente
    if nuevo:
        repo.get.side_effect = servicio.NotFoundError
    persistido = repo.return_value if nuevo else existente
    if error_ttl:
        persistido.expire.side_effect = RuntimeError('redis indisponible')
    datos = ActualizarUbicacion(latitud=-27.4, longitud=-59, timestamp_ubicacion=AHORA)
    resultado, es_nuevo = servicio.ActualizarUbicacionService.procesar(ID, datos)
    assert es_nuevo is nuevo
    assert resultado.conductor_id == ID
    assert resultado.timestamp_ubicacion == AHORA
    assert resultado.recibida_en == AHORA.replace(tzinfo=None)
    assert resultado.expira_en == AHORA + timedelta(seconds=30)
    assert resultado.vigente is True
    repo.get.assert_called_once_with(str(ID))
    persistido.save.assert_called_once_with()
    persistido.expire.assert_called_once_with(30)
    geo = Coordenada(latitud=-27.4, longitud=-59)
    if nuevo:
        repo.assert_called_once_with(pk=str(ID), conductor_id=ID, geo=geo, timestamp_ubicacion=AHORA)
    else:
        repo.assert_not_called()
        assert existente.geo == geo
        assert existente.timestamp_ubicacion == AHORA


def test_get_devuelve_none_crea(servicio):
    servicio.UbicacionesCond.get.return_value = None
    datos = ActualizarUbicacion(latitud=0, longitud=0, timestamp_ubicacion=AHORA)
    assert servicio.ActualizarUbicacionService.procesar(ID, datos)[1] is True


@pytest.mark.parametrize('segundos,latitud,longitud', [(-1, 0, 0), (0, 1, 0), (0, 0, 1)])
def test_rechaza_timestamp_anterior_o_coordenadas_distintas(servicio, segundos, latitud, longitud):
    existente = Mock(timestamp_ubicacion=AHORA, geo=Coordenada(latitud=0, longitud=0))
    servicio.UbicacionesCond.get.return_value = existente
    datos = ActualizarUbicacion(latitud=latitud, longitud=longitud,
        timestamp_ubicacion=AHORA + timedelta(seconds=segundos))
    with pytest.raises(ErrorTimeStamp) as exc:
        servicio.ActualizarUbicacionService.procesar(ID, datos)
    assert exc.value.status_code == 409
    existente.save.assert_not_called()
    existente.expire.assert_not_called()
    servicio.UbicacionesCond.assert_not_called()


def test_mismo_timestamp_mismas_coordenadas(servicio):
    existente = Mock(timestamp_ubicacion=AHORA, geo=Coordenada(latitud=0, longitud=0))
    servicio.UbicacionesCond.get.return_value = existente
    datos = ActualizarUbicacion(latitud=0, longitud=0, timestamp_ubicacion=AHORA)
    assert servicio.ActualizarUbicacionService.procesar(ID, datos)[1] is False
    existente.save.assert_called_once_with()


@pytest.mark.parametrize('etapa', ['get', 'save'])
def test_no_oculta_errores_de_persistencia(servicio, etapa):
    existente = Mock(timestamp_ubicacion=AHORA - timedelta(seconds=1))
    servicio.UbicacionesCond.get.return_value = existente
    objetivo = servicio.UbicacionesCond.get if etapa == 'get' else existente.save
    objetivo.side_effect = RuntimeError('persistencia fallida')
    with pytest.raises(RuntimeError, match='persistencia fallida'):
        servicio.ActualizarUbicacionService.procesar(ID,
            ActualizarUbicacion(latitud=0, longitud=0, timestamp_ubicacion=AHORA))
    existente.expire.assert_not_called()
