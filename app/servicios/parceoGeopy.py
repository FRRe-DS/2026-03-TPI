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

# Variables para control de velocidad (Rate Limiting seguro para hilos)
_lock = threading.Lock()
_ultimo_tiempo_consulta = 0.0
TIEMPO_ESPERA_SEGUNDOS = 1.1

# Configuramos un logger basico para registrar errores si ocurren
acceso = logging.getLogger(__name__)

# realizamos variable que comunica con servidor publico, geopy lo exije
geoConsulta = Nominatim(user_agent="m4_transporte_app") 

ZONA_PERMITIDA = {
    "lat_min": -28.5000,  # Límite Sur (ej: zona Empedrado)
    "lat_max": -27.2000,  # Límite Norte (ej: norte de Resistencia)
    "lon_min": -59.5000,  # Límite Oeste 
    "lon_max": -58.7000   # Límite Este
}

def obtener_coordenadas(direccion: str) -> tuple[float, float]: #retorna tupla (lat,lon) en ese orden
    '''
        Convierte una direccion de texto en una tupla (lat, lon).
        Lanza ValueError si la direccion es invalida o la API falla.
    '''
    global _ultimo_tiempo_consulta
    if not direccion or not direccion.strip(): #no hay string de entrada
        raise ValueError("La direccion proporcionada está vacia.")
    
    cuadrante_busqueda = [(ZONA_PERMITIDA["lat_max"], ZONA_PERMITIDA["lon_min"]),
                        (ZONA_PERMITIDA["lat_min"], ZONA_PERMITIDA["lon_max"]),]            
    
    with _lock:
        tiempo_actual = time.time()
        tiempo_transcurrido = tiempo_actual - _ultimo_tiempo_consulta

        # Si pasó menos de 1 segundo desde la última consulta, obligamos a esperar el resto
        if tiempo_transcurrido < TIEMPO_ESPERA_SEGUNDOS:
            tiempo_a_dormir = TIEMPO_ESPERA_SEGUNDOS - tiempo_transcurrido
            time.sleep(tiempo_a_dormir)
        #si es su "tiempo" entonces no entra al if y pasa a intentar la solicitud
        try:
            
            #timeout=5 evita que el hilo se quede colgado indefinidamente
            #viewbox le pasamos parametros limitantes a el servidor publico para que busque solo en esa region
            #bounded confirmacion de ligacion entre la busqueda del string y cuadrante limitado
            ubicacion = geoConsulta.geocode(direccion,viewbox=cuadrante_busqueda,bounded=True, timeout=5)
            # Actualizamos el timestamp *justo después* de que se completa la llamada
            _ultimo_tiempo_consulta = time.time()
            if not ubicacion: #el servidor publico no encontro macheo o coincidencia sobre el string de entrada
                raise ValueError(f"No se encontro ninguna coincidencia dentro de la limitacion geografica resistencia-ctes para: '{direccion}'")

            return (ubicacion.latitude, ubicacion.longitude)

        except (GeocoderTimedOut, GeopyError): #el servidor no devuelve respuesta o nos bloquea la ip
            # Actualizamos el timestamp igual para no reintentar instantáneamente si falló por timeout
            _ultimo_tiempo_consulta = time.time()
            raise ValueError("El servicio de mapas externo tardo demasiado o no esta disponible.")