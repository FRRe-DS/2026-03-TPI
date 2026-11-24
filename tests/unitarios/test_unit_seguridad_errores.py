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
    (e.DependenciaNoDisponible, 503, 'DEPENDENCIA_NO_DISPONIBLE'),
    (e.FaltaHeaderIdempotencia, 400, 'HEADER_IDEMPOTENCIA_FALTANTE'),
    (e.HashBodyDiferente, 422, 'IDEMPOTENCIA_CONFLICTO'),
    (e.ErrorTimeStamp, 409, 'CONFLICTO_TIMESTAMP'),
    (e.ErrorHealthCheck, 503, 'HEALTH_CHECK_FALLO'),
])
def test_excepciones_concretas(clase, status, codigo):
    error = clase()
    assert error.status == status
    assert error.code == codigo
    assert error.title
    assert str(error) == error.detail
    assert error.detail
    assert clase(detail='detalle personalizado').detail == 'detalle personalizado'


@pytest.mark.parametrize('clase', [e.ProblemaGenerico, e.ProblemaDominio])
def test_atributos_completos_y_limites(clase):
    for status in (400, 599):
        datos = dict(type='/error', title='Error', status=status, detail='detalle',
            instance='/recurso', code='CODIGO', trace_id='traza', invalid_params=[{'name': 'campo'}])
        error = clase(**datos)
        assert all(getattr(error, k) == v for k, v in datos.items())
        assert str(error) == 'detalle'
    for status in (399, 600):
        with pytest.raises(ValueError, match=str(status)):
            clase(status=status)


@pytest.fixture
def idempotencia(cargar_aislado):
    modulo = cargar_aislado('app.seguridad.idempotenciaManager')
    modulo.cache.get.return_value = None
    return modulo


@pytest.mark.parametrize('header', [None, ''])
def test_header_obligatorio_sin_http(idempotencia, header):
    request = SimpleNamespace(
        headers={'Idempotency-Key': header},
        state=SimpleNamespace(request_id='unit-test'),
        body=AsyncMock(),
    )
    with pytest.raises(e.FaltaHeaderIdempotencia):
        asyncio.run(idempotencia.verificar_idempotencia(request))
    request.body.assert_not_awaited()
    idempotencia.cache.get.assert_not_called()


def test_clave_nueva(idempotencia):
    request = SimpleNamespace(
        headers={'Idempotency-Key': 'clave'},
        state=SimpleNamespace(request_id='unit-test'),
        body=AsyncMock(return_value=b'{}'),
    )
    assert asyncio.run(idempotencia.verificar_idempotencia(request)) == ('clave', hashlib.sha256(b'{}').hexdigest())
    request.body.assert_awaited_once_with()
    idempotencia.cache.get.assert_called_once_with('idempotency:clave')


@pytest.mark.parametrize('mismo_body', [True, False])
def test_reintento_y_conflicto(idempotencia, mismo_body):
    body = b'{}'
    hash_original = hashlib.sha256(body).hexdigest() if mismo_body else 'otro'
    idempotencia.cache.get.return_value = '{"registro":"cacheado"}'
    idempotencia.RegistroIdempotencia.model_validate_json.return_value = SimpleNamespace(
        body_hash=hash_original, status_code=201, body={'ok': True})
    request = SimpleNamespace(
        headers={'Idempotency-Key': 'clave'},
        state=SimpleNamespace(request_id='unit-test'),
        body=AsyncMock(return_value=body),
    )
    if mismo_body:
        with pytest.raises(idempotencia.RespuestaIdempotenteLista) as respuesta:
            asyncio.run(idempotencia.verificar_idempotencia(request))
        assert respuesta.value.status_code == 201
        assert respuesta.value.payload == {'ok': True}
    else:
        with pytest.raises(e.HashBodyDiferente) as error:
            asyncio.run(idempotencia.verificar_idempotencia(request))
        assert error.value.status == 422


def test_guardar_respuesta_con_clave_y_ttl(idempotencia):
    registro = idempotencia.RegistroIdempotencia.return_value
    registro.model_dump_json.return_value = '{"status_code":201}'

    idempotencia.guardar_respuesta_idempotente(
        'clave', 'hash', 201, {'ok': True}, trace_id='unit-test')

    idempotencia.RegistroIdempotencia.assert_called_once_with(
        status_code=201, body={'ok': True}, body_hash='hash')
    idempotencia.cache.set.assert_called_once_with(
        'idempotency:clave', '{"status_code":201}', ex=10800)


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
    assert len(registrados) == 5
    return registrados


@pytest.mark.parametrize('clase', [e.ProblemaGenerico, e.ProblemaDominio])
@pytest.mark.parametrize('opcionales', [False, True])
def test_formato_problem_json_sin_app(manejadores, clase, opcionales):
    error = clase(status=409, detail='conflicto', title='Conflicto',
        code='CODIGO' if opcionales else None, invalid_params=[] if opcionales else None)
    request = SimpleNamespace(state=SimpleNamespace(request_id='traza'), url=SimpleNamespace(path='/recurso'))
    respuesta = asyncio.run(manejadores[clase](request, error))
    esperado = dict(type=error.type, title='Conflicto', status=409, detail='conflicto',
        instance='/recurso', trace_id='traza')
    if opcionales:
        esperado.update(code='CODIGO', invalid_params=[])
    assert json.loads(respuesta.body) == esperado
    assert respuesta.status_code == error.status
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
