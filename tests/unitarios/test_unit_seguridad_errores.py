import asyncio
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.exceptions import RequestValidationError

from app.errores import exceptionsSemanticos as e
from app.errores.handlerManager import registrar_manejadores_excepciones


@pytest.mark.parametrize('clase,status,codigo', [
    (e.NoAutenticado, 401, 'NO_AUTENTICADO'),
    (e.SinPermiso, 403, 'SIN_PERMISO'),
    (e.DependenciaNoDisponible, 503, 'GEOCODIFICACION_FRACASO'),
    (e.FaltaHeaderIdempotencia, 400, 'HEADER_IDEMPOTENCIA_FALTANTE'),
    (e.HashBodyDiferente, 409, 'IDEMPOTENCIA_CONFLICTO'),
    (e.ErrorTimeStamp, 409, 'CONFLICTO_TIMESTAMP'),
    (e.ErrorHealthCheck, 503, 'HEALTH_CHECK_FALLO'),
])
def test_excepciones_concretas(clase, status, codigo):
    error = clase()
    assert error.status_code == status
    assert error.code == codigo
    assert error.title
    assert str(error) == error.detail
    assert error.detail
    assert clase(detail='detalle personalizado').detail == 'detalle personalizado'


@pytest.mark.parametrize('clase', [e.ProblemaGenerico, e.ProblemaDominio,
    e.NoProcesable, e.LimiteExcedido, e.ErrorInterno, e.TiempoAgotado])
def test_atributos_completos_y_limites(clase):
    for status in (400, 599):
        datos = dict(type='/error', title='Error', status_code=status, detail='detalle',
            instance='/recurso', code='CODIGO', trace_id='traza', invalid_params=[{'name': 'campo'}])
        error = clase(**datos)
        assert all(getattr(error, k) == v for k, v in datos.items())
        assert str(error) == 'detalle'
    for status in (399, 600):
        with pytest.raises(ValueError, match=str(status)):
            clase(status_code=status)


@pytest.fixture
def idempotencia(cargar_aislado):
    modulo = cargar_aislado('app.seguridad.idempotenciaManager')
    modulo.cache.get.return_value = None
    return modulo


@pytest.mark.parametrize('header', [None, ''])
def test_header_obligatorio_sin_http(idempotencia, header):
    request = SimpleNamespace(headers={'idempotencyKey': header}, body=AsyncMock())
    with pytest.raises(e.FaltaHeaderIdempotencia):
        asyncio.run(idempotencia.verificar_idempotencia(request, Mock()))
    request.body.assert_not_awaited()
    idempotencia.cache.get.assert_not_called()


def test_clave_nueva(idempotencia):
    request = SimpleNamespace(headers={'idempotencyKey': 'clave'}, body=AsyncMock(return_value=b'{}'))
    assert asyncio.run(idempotencia.verificar_idempotencia(request, Mock())) == 'clave'
    request.body.assert_awaited_once_with()
    idempotencia.cache.get.assert_called_once_with('idempotency:clave')


@pytest.mark.parametrize('mismo_body', [True, False])
@pytest.mark.xfail(strict=True, raises=AttributeError,
    reason='Lee coincidencia.body_hash de un str y campo.status_code en vez de campo.status')
def test_reintento_y_conflicto(idempotencia, mismo_body):
    body = b'{}'
    hash_original = hashlib.sha256(body).hexdigest() if mismo_body else 'otro'
    idempotencia.cache.get.return_value = '{"registro":"cacheado"}'
    idempotencia.RegistroIdempotencia.model_validate_json.return_value = SimpleNamespace(
        body_hash=hash_original, status=201, body={'ok': True})
    request = SimpleNamespace(headers={'idempotencyKey': 'clave'}, body=AsyncMock(return_value=body))
    if mismo_body:
        respuesta = asyncio.run(idempotencia.verificar_idempotencia(request, Mock()))
        assert respuesta.status_code == 201
        assert json.loads(respuesta.body) == {'ok': True}
    else:
        with pytest.raises(e.HashBodyDiferente):
            asyncio.run(idempotencia.verificar_idempotencia(request, Mock()))


@pytest.fixture
def manejadores():
    registrados = {}
    app = Mock()
    def registrar(clase):
        def decorador(funcion):
            registrados[clase] = funcion
            return funcion
        return decorador
    app.exception_handler.side_effect = registrar
    registrar_manejadores_excepciones(app)
    assert len(registrados) == 4
    return registrados


@pytest.mark.parametrize('clase', [e.ProblemaGenerico, e.ProblemaDominio])
@pytest.mark.parametrize('opcionales', [False, True])
def test_formato_problem_json_sin_app(manejadores, clase, opcionales):
    error = clase(status_code=409, detail='conflicto', title='Conflicto',
        code='CODIGO' if opcionales else None, invalid_params=[] if opcionales else None)
    request = SimpleNamespace(state=SimpleNamespace(request_id='traza'), url=SimpleNamespace(path='/recurso'))
    respuesta = asyncio.run(manejadores[clase](request, error))
    esperado = dict(type=error.type, title='Conflicto', status=409, detail='conflicto',
        instance='/recurso', trace_id='traza')
    if opcionales:
        esperado.update(code='CODIGO', invalid_params=[])
    assert json.loads(respuesta.body) == esperado
    assert respuesta.status_code == 409
    assert respuesta.headers['content-type'] == 'application/problem+json'


def test_formato_errores_pydantic(manejadores):
    request = SimpleNamespace(state=SimpleNamespace(), url=SimpleNamespace(path='/recurso'))
    error = RequestValidationError([{'loc': ('body', 'latitud'), 'msg': 'Fuera de rango', 'type': 'value_error'}])
    respuesta = asyncio.run(manejadores[RequestValidationError](request, error))
    datos = json.loads(respuesta.body)
    assert respuesta.status_code == 422
    assert datos['invalid_params'] == [{'name': 'body -> latitud', 'reason': 'Fuera de rango'}]
    assert datos['trace_id'] is None
    assert datos['instance'] == '/recurso'


def test_error_inesperado(manejadores):
    request = SimpleNamespace(state=SimpleNamespace(), url=SimpleNamespace(path='/recurso'))
    respuesta = asyncio.run(manejadores[Exception](request, RuntimeError('dato interno')))
    datos = json.loads(respuesta.body)
    assert respuesta.status_code == 500
    assert datos['title'] == 'Error Interno del Servidor'
    assert 'dato interno' not in datos['detail']
