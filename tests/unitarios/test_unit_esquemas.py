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
    (e.ConsultaGeocodificacion, dict(direccion=' Plaza ', localidad=' Resistencia ', pais='AR')),
    (e.CoincidenciasGeolocalizacion, dict(**GEO, etiqueta='Plaza', confianza=0.9)),
    (e.ResultadoGeocodificacion, dict(coincidencias=[dict(**GEO, etiqueta='Plaza', confianza=1)])),
    (e.QueryEstimacionRuta, dict(origen_latitud=0, origen_longitud=0,
        destino_latitud=1, destino_longitud=1, tipo_vehiculo='AUTO')),
    (e.ResultadoEstimacionRuta, dict(distancia_estimada_km=0, eta_minutos=0,
        calculado_en=AHORA, fuente='estimacion_local')),
    (e.CambioReservaTemporal, dict(estado_temporal='RESERVADO', solicitud_id=ID)),
    (e.ResultadoReservaTemporal, dict(conductor_id=ID, solicitud_id=ID,
        estado_temporal='RESERVADO', actualizado_en=AHORA)),
    (e.EstadoOperativo, dict(event_id=ID, connected=True, available=True,
        timestamp_evento=AHORA)),
    (e.EstadoOperativoRegistrado, dict(conductor_id=ID, event_id=ID,
        connected=True, available=True, recibido_en=AHORA)),
    (e.QueryCercanos, dict(origen_latitud=0, origen_longitud=0, tipo_vehiculo='AUTO')),
    (e.Candidatos, dict(conductor_id=ID, distancia_origen_km=0, tipo_vehiculo='AUTO')),
    (e.ResultadoBusquedaConductores, dict(conductores=[], radio_aplicado_km=5,
        generado_en=AHORA)),
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


@pytest.mark.parametrize('campo', ['direccion', 'pais'])
@pytest.mark.parametrize('valor', ['', ' ', '  ', '\t\n'])
def test_textos_requeridos_no_vacios(campo, valor):
    datos = dict(direccion='Plaza', pais='AR')
    datos[campo] = valor
    with pytest.raises(ValidationError):
        e.ConsultaGeocodificacion(**datos)


def test_localidad_opcional_y_normalizacion():
    consulta = e.ConsultaGeocodificacion(
        direccion=' Plaza ', localidad=' Resistencia ', pais='AR')
    assert (consulta.direccion, consulta.localidad, consulta.pais) == (
        'Plaza', 'Resistencia', 'ar')
    assert e.ConsultaGeocodificacion(direccion='Plaza', pais='AR').localidad is None


def test_limites_de_texto_del_contrato():
    assert len(e.ConsultaGeocodificacion(direccion='x' * 300, pais='AR').direccion) == 300
    with pytest.raises(ValidationError):
        e.ConsultaGeocodificacion(direccion='x' * 301, pais='AR')
    with pytest.raises(ValidationError):
        e.ConsultaGeocodificacion(direccion='Plaza', localidad='x' * 121, pais='AR')


def test_expiracion_de_ubicacion_es_opcional():
    datos = {k: v for k, v in CASOS[2][1].items() if k != 'expira_en'}
    assert e.UbicacionRegistrada(**datos).expira_en is None


@pytest.mark.parametrize('pais', ['a', 'arg', ' ar ', ''])
def test_longitud_pais(pais):
    with pytest.raises(ValidationError):
        e.ConsultaGeocodificacion(direccion='Plaza', pais=pais)


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
    (e.CambioReservaTemporal, CASOS[8][1], 'estado_temporal', 'OTRO'),
    (e.CambioReservaTemporal, CASOS[8][1], 'solicitud_id', 'uuid-invalido'),
    (e.ActualizarUbicacion, CASOS[1][1], 'timestamp_ubicacion', 'ayer'),
    (e.QueryEstimacionRuta, CASOS[6][1], 'tipo_vehiculo', 'BICI'),
    (e.ResultadoEstimacionRuta, CASOS[7][1], 'fuente', 'OTRA'),
    (e.EstadoOperativo, CASOS[10][1], 'event_id', 'uuid-invalido'),
    (e.Candidatos, CASOS[13][1], 'distancia_origen_km', -0.01),
])
def test_tipos_y_enumeraciones_invalidos(modelo, datos, campo, valor):
    with pytest.raises(ValidationError):
        modelo(**{**datos, campo: valor})


def test_valores_enum_y_campos_opcionales_del_contrato():
    assert e.CambioReservaTemporal(**CASOS[8][1]).estado_temporal == e.EstadoTmp.RESERVADO
    assert e.CambioReservaTemporal(**{**CASOS[8][1], 'estado_temporal': 'LIBERADO'}).estado_temporal == e.EstadoTmp.LIBERADO
    assert e.ResultadoGeocodificacion(coincidencias=[]).coincidencias == []
    assert e.QueryEstimacionRuta(**{**CASOS[6][1], 'tipo_vehiculo': 'MOTO'}).tipo_vehiculo == e.VehiculosSoportados.MOTO
    assert e.QueryEstimacionRuta(**{k: v for k, v in CASOS[6][1].items() if k != 'tipo_vehiculo'}).tipo_vehiculo is None
    assert e.ResultadoEstimacionRuta(**{**CASOS[7][1], 'fuente': 'proveedor_mapa'}).fuente == e.FuenteInfo.PROVEEDOR_MAPA
    assert e.CoincidenciasGeolocalizacion(**GEO, etiqueta='Plaza').confianza is None
