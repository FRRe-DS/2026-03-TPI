"""Contrato mínimo pendiente; RegistrarReserva carece de entradas y persistencia."""
from unittest.mock import patch

import pytest

from app.esquemas.esquemas import SolicitudReserva, EstadoTmp
from app.servicios.manejarReserva import RegistrarReserva


@pytest.mark.xfail(strict=True, raises=AssertionError,
    reason='RegistrarReserva es pass: no existen repositorio ni transiciones de estado')
def test_registro_genera_reserva_en_estado_reservado():
    with patch('socket.socket', side_effect=AssertionError('No se permite red')):
        resultado = RegistrarReserva()
    assert isinstance(resultado, SolicitudReserva)
    assert resultado.estado == EstadoTmp.RESERVADO
