from types import SimpleNamespace
from unittest.mock import Mock, mock_open, patch

import pytest
from geopy.exc import GeocoderTimedOut, GeopyError

from app.esquemas.esquemas import ConsultaGeocodificacion
from app.errores.exceptionsSemanticos import DependenciaNoDisponible
from app.servicios.cadenaDeProveedores import AdaptadorEncadenado
from app.servicios.geocodif_diccionario import Dicc_geocodif
from app.servicios.geocodif_Geopy import ProovedorGeoRef_Geopy

CONSULTA = ConsultaGeocodificacion(direccion='Plaza', provincia='Chaco', pais='ar')
COINCIDENCIA = dict(latitud=-27.4, longitud=-59, etiqueta='Plaza', confianza=1)


@pytest.fixture
def cadena():
    with patch('app.servicios.cadenaDeProveedores.Dicc_geocodif') as local, \
         patch('app.servicios.cadenaDeProveedores.ProovedorGeoRef_Geopy') as externo:
        instancia = AdaptadorEncadenado()
        assert instancia.proveedorLocal is local.return_value
        assert instancia.proveedorExt is externo.return_value
        yield instancia


def test_prioridad_local(cadena):
    esperado = {'coincidencias': [COINCIDENCIA]}
    cadena.proveedorLocal.buscar.return_value = esperado
    assert cadena.resolver(CONSULTA) is esperado
    cadena.proveedorLocal.buscar.assert_called_once_with(CONSULTA)
    cadena.proveedorExt.buscar.assert_not_called()


@pytest.mark.parametrize('local', [{}, {'coincidencias': []}])
@pytest.mark.parametrize('externo', [{'coincidencias': []}, {'coincidencias': [COINCIDENCIA]}])
def test_fallback_y_ambos_vacios(cadena, local, externo):
    cadena.proveedorLocal.buscar.return_value = local
    cadena.proveedorExt.buscar.return_value = externo
    assert cadena.resolver(CONSULTA) is externo
    cadena.proveedorExt.buscar.assert_called_once_with(CONSULTA)


def test_error_externo_es_de_negocio(cadena):
    cadena.proveedorLocal.buscar.return_value = {'coincidencias': []}
    cadena.proveedorExt.buscar.side_effect = DependenciaNoDisponible()
    with pytest.raises(DependenciaNoDisponible):
        cadena.resolver(CONSULTA)


@pytest.mark.xfail(strict=True, raises=OSError, reason='La cadena no captura fallos del proveedor local')
def test_fallback_si_local_falla(cadena):
    cadena.proveedorLocal.buscar.side_effect = OSError('archivo ilegible')
    cadena.proveedorExt.buscar.return_value = {'coincidencias': [COINCIDENCIA]}
    assert cadena.resolver(CONSULTA) == {'coincidencias': [COINCIDENCIA]}
    cadena.proveedorExt.buscar.assert_called_once_with(CONSULTA)


@pytest.mark.parametrize('existe,contenido,esperado', [
    (True, '{"nea": []}', {'nea': []}), (False, '', {}), (True, 'json roto', {}),
])
def test_carga_archivo_aislada(existe, contenido, esperado):
    with patch('app.servicios.geocodif_diccionario.Path.exists', return_value=existe), \
         patch('builtins.open', mock_open(read_data=contenido)) as abrir:
        assert Dicc_geocodif('virtual.json').ubicaciones_conocidas == esperado
        if existe:
            abrir.assert_called_once()
        else:
            abrir.assert_not_called()


def test_error_lectura():
    with patch('app.servicios.geocodif_diccionario.Path.exists', return_value=True), \
         patch('builtins.open', side_effect=OSError('sin permiso')):
        assert Dicc_geocodif('virtual.json').ubicaciones_conocidas == {}


@pytest.mark.parametrize('texto,esperado', [('', ''), ('  ÁRBOL Ñandú  ', 'arbol nandu')])
def test_normalizacion(texto, esperado):
    assert Dicc_geocodif._normalizar_texto(texto) == esperado


@pytest.mark.parametrize('direccion,numero', [('Plaza', 1), ('Plaza central de la ciudad', 1), ('Desconocido', 0), ('', 0)])
def test_busqueda_local_y_alias_sin_duplicados(direccion, numero):
    datos = {'nea': [{**COINCIDENCIA, 'alias': ['otro', 'Plaza central', 'Plaza']}]}
    with patch.object(Dicc_geocodif, '_cargar_en_memoria', return_value=datos):
        proveedor = Dicc_geocodif()
    # Namespace permite cubrir defensas internas que Pydantic impide alcanzar.
    resultado = proveedor.buscar(SimpleNamespace(direccion=direccion, provincia='', pais=''))
    assert resultado == {'coincidencias': [COINCIDENCIA] * numero}


@pytest.fixture
def geopy():
    with patch('app.servicios.geocodif_Geopy.Nominatim') as constructor, \
         patch('app.servicios.geocodif_Geopy.time.time', return_value=100), \
         patch('app.servicios.geocodif_Geopy.time.sleep') as dormir:
        proveedor = ProovedorGeoRef_Geopy(user_agent='unitarios')
        constructor.assert_called_once_with(user_agent='unitarios')
        yield proveedor, dormir


@pytest.mark.parametrize('importance,esperado', [(None, 1), (-1, 0), (2, 1), (0.4, 0.4)])
def test_mapeo_geopy_y_parametros(geopy, importance, esperado):
    proveedor, dormir = geopy
    proveedor.servicioExt.geocode.return_value = [SimpleNamespace(
        latitude=-27.4, longitude=-59, address='Plaza', raw={'importance': importance})]
    assert proveedor.buscar(CONSULTA) == {'coincidencias': [{**COINCIDENCIA, 'confianza': esperado}]}
    proveedor.servicioExt.geocode.assert_called_once_with('Plaza, Chaco',
        viewbox=[(-27.2, -59.5), (-28.5, -58.7)], bounded=True,
        country_codes='ar', exactly_one=False, timeout=5)
    dormir.assert_not_called()
    assert proveedor._ultimo_tiempo_consulta == 100


@pytest.mark.parametrize('vacio', [None, []])
def test_geopy_sin_resultados_y_rate_limit(geopy, vacio):
    proveedor, dormir = geopy
    proveedor._ultimo_tiempo_consulta = 99.5
    proveedor.servicioExt.geocode.return_value = vacio
    consulta = SimpleNamespace(direccion='Plaza', provincia='', pais='ar')
    assert proveedor.buscar(consulta) == {'coincidencias': []}
    dormir.assert_called_once_with(1.0)
    assert proveedor.servicioExt.geocode.call_args.args == ('Plaza',)


@pytest.mark.parametrize('error', [GeocoderTimedOut, GeopyError])
def test_geopy_traduce_error_y_actualiza_reloj(geopy, error):
    proveedor, _ = geopy
    proveedor.servicioExt.geocode.side_effect = error('fallo')
    with pytest.raises(DependenciaNoDisponible) as exc:
        proveedor.buscar(CONSULTA)
    assert exc.value.status_code == 503
    assert proveedor._ultimo_tiempo_consulta == 100
