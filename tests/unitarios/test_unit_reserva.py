from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from uuid import UUID

import pytest

from app.errores.exceptionsSemanticos import ErrorConflicto, RecursoNoDisponible
from app.esquemas.esquemas import CambioReservaTemporal, EstadoTmp

CONDUCTOR_ID = UUID('00000000-0000-0000-0000-000000000001')
SOLICITUD_ID = UUID('00000000-0000-0000-0000-000000000002')
OTRA_SOLICITUD_ID = UUID('00000000-0000-0000-0000-000000000003')
AHORA = datetime(2026, 1, 1, tzinfo=timezone.utc)
TRACE_ID = 'unit-test'


@pytest.fixture
def servicio(cargar_aislado):
    modulo = cargar_aislado('app.servicios.manejarReserva')
    with patch.object(modulo, 'datetime') as reloj:
        reloj.now.return_value = AHORA
        yield modulo


def test_crear_reserva_temporal_con_ttl(servicio):
    servicio.CacheResTemp.get.side_effect = servicio.NotFoundError
    registro = servicio.CacheResTemp.instance
    datos = CambioReservaTemporal(solicitud_id=SOLICITUD_ID, estado_temporal='RESERVADO')

    resultado, es_nueva = servicio.ReservaService.cambiar_reserva(
        CONDUCTOR_ID, datos, TRACE_ID)

    assert es_nueva is True
    assert resultado.conductor_id == CONDUCTOR_ID
    assert resultado.solicitud_id == SOLICITUD_ID
    assert resultado.estado_temporal == EstadoTmp.RESERVADO
    assert resultado.actualizado_en == AHORA
    assert resultado.expira_en == AHORA + timedelta(minutes=10)
    assert resultado.idempotente is False
    servicio.CacheResTemp.constructor.assert_called_once_with(
        pk=str(CONDUCTOR_ID),
        conductor_id=CONDUCTOR_ID,
        solicitud_id=SOLICITUD_ID,
        estado_temporal=EstadoTmp.RESERVADO,
        actualizado_en=AHORA,
        expira_en=AHORA + timedelta(minutes=10),
    )
    registro.save.assert_called_once_with()
    registro.expire.assert_called_once_with(600)


def test_reservar_de_nuevo_misma_solicitud_no_extiende_ttl(servicio):
    actual = Mock(
        conductor_id=CONDUCTOR_ID,
        solicitud_id=SOLICITUD_ID,
        estado_temporal=EstadoTmp.RESERVADO,
        actualizado_en=AHORA,
        expira_en=AHORA + timedelta(minutes=10),
    )
    servicio.CacheResTemp.get.return_value = actual
    datos = CambioReservaTemporal(solicitud_id=SOLICITUD_ID, estado_temporal='RESERVADO')

    resultado, es_nueva = servicio.ReservaService.cambiar_reserva(
        CONDUCTOR_ID, datos, TRACE_ID)

    assert es_nueva is False
    assert resultado.idempotente is True
    assert resultado.expira_en == AHORA + timedelta(minutes=10)
    actual.save.assert_not_called()
    actual.expire.assert_not_called()


def test_reserva_activa_por_otra_solicitud_es_conflicto(servicio):
    servicio.CacheResTemp.get.return_value = Mock(
        solicitud_id=OTRA_SOLICITUD_ID, estado_temporal=EstadoTmp.RESERVADO)
    datos = CambioReservaTemporal(solicitud_id=SOLICITUD_ID, estado_temporal='RESERVADO')

    with pytest.raises(ErrorConflicto) as error:
        servicio.ReservaService.cambiar_reserva(CONDUCTOR_ID, datos, TRACE_ID)
    assert error.value.status == 409
    assert error.value.code == 'CONDUCTOR_RESERVADO'
    servicio.CacheResTemp.constructor.assert_not_called()


def test_liberar_reserva_actualiza_sin_borrar_registro(servicio):
    actual = Mock(
        conductor_id=CONDUCTOR_ID,
        solicitud_id=SOLICITUD_ID,
        estado_temporal=EstadoTmp.RESERVADO,
        actualizado_en=AHORA - timedelta(minutes=1),
        expira_en=AHORA + timedelta(minutes=9),
    )
    servicio.CacheResTemp.get.return_value = actual
    datos = CambioReservaTemporal(solicitud_id=SOLICITUD_ID, estado_temporal='LIBERADO')

    resultado, es_nueva = servicio.ReservaService.cambiar_reserva(
        CONDUCTOR_ID, datos, TRACE_ID)

    assert es_nueva is False
    assert resultado.estado_temporal == EstadoTmp.LIBERADO
    assert resultado.actualizado_en == AHORA
    assert resultado.idempotente is False
    assert actual.estado_temporal == EstadoTmp.LIBERADO
    actual.save.assert_called_once_with()
    actual.expire.assert_called_once_with(600)


def test_liberacion_repetida_es_idempotente(servicio):
    actual = Mock(
        conductor_id=CONDUCTOR_ID,
        solicitud_id=SOLICITUD_ID,
        estado_temporal=EstadoTmp.LIBERADO,
        actualizado_en=AHORA - timedelta(minutes=1),
        expira_en=AHORA + timedelta(minutes=9),
    )
    servicio.CacheResTemp.get.return_value = actual
    datos = CambioReservaTemporal(solicitud_id=SOLICITUD_ID, estado_temporal='LIBERADO')

    resultado, es_nueva = servicio.ReservaService.cambiar_reserva(
        CONDUCTOR_ID, datos, TRACE_ID)

    assert es_nueva is False
    assert resultado.estado_temporal == EstadoTmp.LIBERADO
    assert resultado.idempotente is True
    actual.save.assert_not_called()
    actual.expire.assert_not_called()


def test_liberar_sin_reserva_responde_no_encontrado(servicio):
    servicio.CacheResTemp.get.side_effect = servicio.NotFoundError
    datos = CambioReservaTemporal(solicitud_id=SOLICITUD_ID, estado_temporal='LIBERADO')

    with pytest.raises(RecursoNoDisponible) as error:
        servicio.ReservaService.cambiar_reserva(CONDUCTOR_ID, datos, TRACE_ID)
    assert error.value.status == 404


def test_no_se_reabre_reserva_liberada(servicio):
    servicio.CacheResTemp.get.return_value = Mock(
        solicitud_id=SOLICITUD_ID, estado_temporal=EstadoTmp.LIBERADO)
    datos = CambioReservaTemporal(solicitud_id=SOLICITUD_ID, estado_temporal='RESERVADO')

    with pytest.raises(ErrorConflicto) as error:
        servicio.ReservaService.cambiar_reserva(CONDUCTOR_ID, datos, TRACE_ID)
    assert error.value.status == 409
