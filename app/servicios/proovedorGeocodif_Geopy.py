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

from geopy.exc import GeocoderTimedOut, GeopyError
from geopy.geocoders import Nominatim
import logging
import threading
import time
from app.errores.exceptionsSemanticos import DependenciaNoDisponible
from app.esquemas.esquemas import ConsultaGeocodificacion
from app.servicios.adaptador import GeoProveedor

class ProovedorGeoRef_Geopy(GeoProveedor):
    def __init__(self, user_agent: str = "m4_transporte_app"):
        self.servicioExt = Nominatim(user_agent=user_agent)
        # Variables para control de velocidad (Rate Limiting seguro para hilos)
        self._lock = threading.Lock()
        self._ultimo_tiempo_consulta = 0.0
        self.TIEMPO_ESPERA_SEGUNDOS = 1.5    
        # Zona permitida (Resistencia / Corrientes)
        self.ZONA_PERMITIDA = {
            "lat_min": -28.5000,
            "lat_max": -27.2000,
            "lon_min": -59.5000,
            "lon_max": -58.7000
        }
        # Configuramos un logger básico para registrar errores si ocurren
        self.logger = logging.getLogger(__name__)

    def buscar(self, body: ConsultaGeocodificacion) -> dict:
        restricciones = f"{body.direccion}, {body.provincia}" if body.provincia else f"{body.direccion}"

        cuadrante_busqueda = [
            (self.ZONA_PERMITIDA["lat_max"], self.ZONA_PERMITIDA["lon_min"]),
            (self.ZONA_PERMITIDA["lat_min"], self.ZONA_PERMITIDA["lon_max"])
        ]            
        
        # Protegemos la llamada síncrona con el lock interno de la clase
        with self._lock:
            tiempo_actual = time.time()
            tiempo_transcurrido = tiempo_actual - self._ultimo_tiempo_consulta
            # Control de espera entre peticiones para el servidor público
            if tiempo_transcurrido < self.TIEMPO_ESPERA_SEGUNDOS:
                tiempo_a_dormir = self.TIEMPO_ESPERA_SEGUNDOS - tiempo_transcurrido
                time.sleep(tiempo_a_dormir)

            # timeout=5 evita que el hilo se cuelgue
            # viewbox y bounded limitan estrictamente al cuadrante de Resistencia/Corrientes
            # exactly_one=False habilita la obtención de una lista con múltiples coincidencias
            try:
                ubicaciones = self.servicioExt.geocode(
                    restricciones,
                    viewbox=cuadrante_busqueda,
                    bounded=True,
                    country_codes=body.pais,
                    exactly_one=False,
                    timeout=5
                )
                
                self._ultimo_tiempo_consulta = time.time()
                # Si el servidor público no encuentra coincidencias, retornamos lista vacía
                if not ubicaciones:
                    return {"coincidencias": []}

                # Aquí se mapeará el resultado bruto de Geopy al formato JSON definitivo que exija el contrato
                geocoincidencias = []
                for loc in ubicaciones:
                    geocoincidencias.append({
                        "latitud": loc.latitude,
                        "longitud": loc.longitude,
                        "etiqueta": loc.address,
                        "confianza": 1
                    })

                return {"coincidencias": geocoincidencias}
            # Actualizamos el timestamp igual para no reintentar instantáneamente si falló
            except (GeocoderTimedOut, GeopyError):
                self._ultimo_tiempo_consulta = time.time()
                raise DependenciaNoDisponible()# 503