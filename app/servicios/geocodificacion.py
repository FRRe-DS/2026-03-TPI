'''
===============================================
Resuelve RF 4.5 GEOCODIFICACION
===============================================
Codigo vinculante a la consulta con el servicio/servidor externo de geolocalizacion con geopy
debe ser invocada desde un procesamiento de eventos unicas de "hilo" del SO, de esa manera no 
congela el resto de peticiones de servidor entre modulos, por ello se implementa cola de espera
para procesar peticiones sin que el servidor nos bloquee.

se debe invocar mediante
lat,long = obtener_coordenadas(direccion)

'''

import logging
from geopy.exc import GeocoderTimedOut, GeopyError
from geopy.geocoders import Nominatim
import threading
import time
from app.servicios.exceptionSemanticos import DependenciaNoDisponible
from app.schemas.schemas import ConsultaGeocodificacion

# Variables para control de velocidad (Rate Limiting seguro para hilos)
_lock = threading.Lock()
_ultimo_tiempo_consulta = 0.0
TIEMPO_ESPERA_SEGUNDOS = 1.5

# Configuramos un logger básico para registrar errores si ocurren
acceso = logging.getLogger(__name__)

# Realizamos variable que comunica con servidor público
geoConsulta = Nominatim(user_agent="m4_transporte_app") 

ZONA_PERMITIDA = {
    "lat_min": -28.5000,  # Límite Sur (ej: zona Empedrado)
    "lat_max": -27.2000,  # Límite Norte (ej: norte de Resistencia)
    "lon_min": -59.5000,  # Límite Oeste 
    "lon_max": -58.7000   # Límite Este
}

def obtener_coordenadas(body:ConsultaGeocodificacion) -> dict: #aqui los parametros deben obedecer al contrato OJO a modificar
    '''
        Convierte una dirección en lenguaje natural, provincia y país en una lista de 
        coincidencias geográficas. Retorna una lista (vacía, con 1 o más elementos).
    '''
    global _ultimo_tiempo_consulta    
    # =========================================================================
    # [ZONA DE INTERVENCIÓN 1: DICCIONARIO LOCAL / CACHÉ DE PRUEBA]
    # Aquí se consultará el diccionario JSON local de ubicaciones "famosas" o 
    # de prueba antes de impactar en Geopy o Redis.
    # Ejemplo a futuro:
    # resultado_diccionario = buscar_en_diccionario_estatico(direccion, provincia, pais)
    # if resultado_diccionario:
    #     return resultado_diccionario
    # =========================================================================

    # Combinamos los campos de entrada para refinar el texto de búsqueda y acotar aciertos
    query_completa = f"{body.direccion}, {body.provincia}" if body.provincia else f"{body.direccion}"

    cuadrante_busqueda = [
        (ZONA_PERMITIDA["lat_max"], ZONA_PERMITIDA["lon_min"]),
        (ZONA_PERMITIDA["lat_min"], ZONA_PERMITIDA["lon_max"])
    ]            
    
    with _lock:
        tiempo_actual = time.time()
        tiempo_transcurrido = tiempo_actual - _ultimo_tiempo_consulta

        # Control de espera entre peticiones para el servidor público
        if tiempo_transcurrido < TIEMPO_ESPERA_SEGUNDOS:
            tiempo_a_dormir = TIEMPO_ESPERA_SEGUNDOS - tiempo_transcurrido
            time.sleep(tiempo_a_dormir)
        
        try:
            # timeout=5 evita que el hilo se cuelgue
            # viewbox y bounded limitan estrictamente al cuadrante de Resistencia/Corrientes
            # exactly_one=False habilita la obtención de una lista con múltiples coincidencias
            ubicaciones = geoConsulta.geocode(
                query_completa,
                viewbox=cuadrante_busqueda,
                bounded=True,
                country_codes=body.pais,
                exactly_one=False,
                timeout=5
            )
            
            # Actualizamos el timestamp justo después de completar la llamada
            _ultimo_tiempo_consulta = time.time()
            
            if not ubicaciones:
                # Si el servidor público no encuentra coincidencias, retornamos lista vacía
                return {"coincidencias": []}

            # =========================================================================
            # [ZONA DE INTERVENCIÓN 2: ADAPTACIÓN DEL FORMATO DE SALIDA]
            # Aquí se mapeará el resultado bruto de Geopy al formato JSON definitivo 
            # que exija el contrato (por ejemplo, estructurado con etiquetas, confianza y UUIDs).
            # =========================================================================
            geocoincidencias = []
            for loc in ubicaciones:
                geocoincidencias.append({
                    "latitud": loc.latitude,
                    "longitud": loc.longitude,
                    "etiqueta": loc.address,
                    "confianza": 1  # Espacio para asignar métrica de confianza si se requiere
                })

            return {"coincidencias": geocoincidencias}

        except (GeocoderTimedOut, GeopyError):
            # Actualizamos el timestamp igual para no reintentar instantáneamente si falló
            _ultimo_tiempo_consulta = time.time()
            raise DependenciaNoDisponible()# 503