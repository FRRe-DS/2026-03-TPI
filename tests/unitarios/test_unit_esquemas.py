from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.esquemas import esquemas as e

ID = UUID('00000000-0000-0000-0000-000000000001')
AHORA = datetime(2026, 1, 1, tzinfo=timezone.utc)
GEO = dict(latitud=-27.45, longitud=-58.99)
CASOS = [
    (e.Coordenada, GEO),
    (e.ActualizarUbicacion, dict(**GEO, timestamp_ubicacion=AHORA)),
    (e.UbicacionRegistrada, dict(conductor_id=ID, timestamp_ubicacion=AHORA,
        recibida_en=AHORA, vigente=True, expira_en=AHORA)),
    (e.ConsultaGeocodificacion, dict(direccion=' Plaza ', provincia=' Chaco ', pais='AR')),
    (e.CoincidenciasGeolocalizacion, dict(**GEO, etiqueta='Plaza', confianza=0.9)),
    (e.ResultadoGeocodificacion, dict(coincidencias=[dict(**GEO, etiqueta='Plaza', confianza=1)])),
    (e.ConsultaEstimacionRuta, dict(origen_latitud=0, origen_longitud=0,
        destino_latitud=1, destino_longitud=1, tipo_vehiculo='AUTO')),
    (e.ResultadoEstimacionRuta, dict(origen=GEO, destino=GEO, distancia_estimada_km=0,
        eta_minutos=0, calculado_en=AHORA, fuente='ESTIMACION LOCAL')),
    (e.SolicitudReserva, dict(reserva_id=ID, conductor_id=ID)),
]


@pytest.mark.parametrize('modelo,datos', CASOS)
def test_contratos_validos_y_serializacion(modelo, datos):
    instancia = modelo(**datos)
    assert modelo.model_validate_json(instancia.model_dump_json()) == instancia


@pytest.mark.parametrize('modelo,datos', CASOS)
def test_cada_campo_obligatorio(modelo, datos):
    for campo, definicion in modelo.model_fields.items():
        if definicion.is_required():
            incompleto = {k: v for k, v in datos.items() if k != campo}
            with pytest.raises(ValidationError) as error:
                modelo(**incompleto)
            assert campo in [x['loc'][0] for x in error.value.errors()]


@pytest.mark.parametrize('campo', ['direccion', 'provincia', 'pais'])
@pytest.mark.parametrize('valor', ['', ' ', '  ', '\t\n'])
def test_textos_vacios(campo, valor):
    datos = dict(direccion='Plaza', provincia='Chaco', pais='ar')
    datos[campo] = valor
    with pytest.raises(ValidationError):
        e.ConsultaGeocodificacion(**datos)


@pytest.mark.parametrize('pais', ['a', 'arg', ' ar ', ''])
def test_longitud_pais(pais):
    with pytest.raises(ValidationError):
        e.ConsultaGeocodificacion(direccion='Plaza', provincia='Chaco', pais=pais)


def test_validadores_normalizan_y_defienden_invocacion_directa():
    consulta = e.ConsultaGeocodificacion(direccion=' Plaza ', provincia=' Chaco ', pais='AR')
    assert (consulta.direccion, consulta.provincia, consulta.pais) == ('Plaza', 'Chaco', 'ar')
    assert e.ConsultaGeocodificacion.validar_codigo_pais(' AR ') == 'ar'
    # Field rechaza longitudes incorrectas antes de alcanzar este validador.
    with pytest.raises(ValueError, match='exactamente 2'):
        e.ConsultaGeocodificacion.validar_codigo_pais('ARG')


COORDENADAS = [(modelo, datos, campo, 90 if 'latitud' in campo else 180)
    for modelo, datos in CASOS for campo in datos
    if 'latitud' in campo or 'longitud' in campo]


@pytest.mark.parametrize('modelo,datos,campo,limite', COORDENADAS)
@pytest.mark.parametrize('signo', [-1, 1])
def test_limites_inclusivos_y_fuera_de_rango(modelo, datos, campo, limite, signo):
    assert getattr(modelo(**{**datos, campo: signo * limite}), campo) == signo * limite
    with pytest.raises(ValidationError):
        modelo(**{**datos, campo: signo * (limite + 0.001)})


@pytest.mark.parametrize('confianza', [-0.01, 1.01])
def test_confianza_fuera_de_rango(confianza):
    with pytest.raises(ValidationError):
        e.CoincidenciasGeolocalizacion(**GEO, etiqueta='Plaza', confianza=confianza)


@pytest.mark.parametrize('modelo,datos,campo,valor', [
    (e.SolicitudReserva, CASOS[-1][1], 'estado', 'OTRO'),
    (e.SolicitudReserva, CASOS[-1][1], 'conductor_id', 'uuid-invalido'),
    (e.ActualizarUbicacion, CASOS[1][1], 'timestamp_ubicacion', 'ayer'),
    (e.ConsultaEstimacionRuta, CASOS[6][1], 'tipo_vehiculo', 'BICI'),
    (e.ResultadoEstimacionRuta, CASOS[7][1], 'fuente', 'OTRA'),
])
def test_tipos_y_enumeraciones_invalidos(modelo, datos, campo, valor):
    with pytest.raises(ValidationError):
        modelo(**{**datos, campo: valor})


def test_estados_y_lista_vacia():
    assert e.SolicitudReserva(**CASOS[-1][1]).estado == e.EstadoTmp.RESERVADO
    assert e.SolicitudReserva(**CASOS[-1][1], estado='LIBERADO').estado == e.EstadoTmp.LIBERADO
    assert e.ResultadoGeocodificacion(coincidencias=[]).coincidencias == []
    assert e.ConsultaEstimacionRuta(**{**CASOS[6][1], 'tipo_vehiculo': 'MOTO'}).tipo_vehiculo == e.VehiculosSoportados.MOTO
    assert e.ResultadoEstimacionRuta(**{**CASOS[7][1], 'fuente': 'MAPA'}).fuente == e.FuenteInfo.MAPA
