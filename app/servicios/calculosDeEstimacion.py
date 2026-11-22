import math
from datetime import datetime, timezone
from geopy.distance import geodesic
from app.esquemas.esquemas import (
    ConsultaEstimacionRuta,
    FuenteInfo,
    ResultadoEstimacionRuta,
    VehiculosSoportados,
)

VELOCIDAD_AUTO_KMH = 30.0
VELOCIDAD_MOTO_KMH = 35.0
FACTOR_RUTAS_URBANAS = 1.3

#TODO: ADAPTAR PARA LOGRAR REGISTRAR LOGS DE TRAZABILIDAD
#TODO: FALTA POSIBILIDAD DE QUE GEOPY FRACASE, Y TIRE ERROR DE DEPENDENCIA AL INTENTAR CALCULAR
def CalculosDeViaje(datos: ConsultaEstimacionRuta) -> ResultadoEstimacionRuta:
    #Estima distancia de ruta y ETA a partir de la distancia geodésica
    origen = (datos.origen_latitud, datos.origen_longitud)
    destino = (datos.destino_latitud, datos.destino_longitud)
    distancia_linea_recta_km = geodesic(origen, destino).kilometers
    distancia_estimada_km = round(distancia_linea_recta_km * FACTOR_RUTAS_URBANAS, 2)

    velocidad_kmh = (VELOCIDAD_MOTO_KMH if datos.tipo_vehiculo == VehiculosSoportados.MOTO else VELOCIDAD_AUTO_KMH)
    
    eta_minutos = max(1, math.ceil((distancia_estimada_km / velocidad_kmh) * 60))
    #TODO: si corresponde utilizar logger para registrar datos, si no fuera confidencial
    return ResultadoEstimacionRuta(
        distancia_estimada_km=distancia_estimada_km,
        eta_minutos=eta_minutos,
        calculado_en=datetime.now(timezone.utc),
        fuente=FuenteInfo.ESTIMACION_LOCAL,)
