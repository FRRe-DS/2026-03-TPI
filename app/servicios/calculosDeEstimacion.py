import math,logging
from datetime import datetime, timezone
from geopy.distance import geodesic
from app.esquemas.esquemas import (QueryEstimacionRuta,FuenteInfo,ResultadoEstimacionRuta,VehiculosSoportados,)
from app.errores.exceptionsSemanticos import DependenciaNoDisponible

logger=logging.getLogger(__name__)

VELOCIDAD_AUTO_KMH = 30.0
VELOCIDAD_MOTO_KMH = 35.0
FACTOR_RUTAS_URBANAS = 1.3

def CalculosDeViaje(datos: QueryEstimacionRuta,trace_id:str) -> ResultadoEstimacionRuta:
    logger.info("[trace_id=%s]|Inicio calculo de estimaciones de tiempo y distancia.",trace_id)
    #Estima distancia de ruta y ETA a partir de la distancia geodésica
    origen = (datos.origen_latitud, datos.origen_longitud)
    destino = (datos.destino_latitud, datos.destino_longitud)

    try:
        distancia_linea_recta_km = geodesic(origen, destino).kilometers
    except Exception as e:
        logger.exception("[trace_id=%s]|Error inesperado de dependencia.|Tipo: %s |Detalle: %s",trace_id,type(e).__name__,e)
        raise DependenciaNoDisponible() from e
    
    distancia_estimada_km = round(distancia_linea_recta_km * FACTOR_RUTAS_URBANAS, 2)
    velocidad_kmh = (VELOCIDAD_MOTO_KMH if datos.tipo_vehiculo == VehiculosSoportados.MOTO else VELOCIDAD_AUTO_KMH)
    eta_minutos = max(1, math.ceil((distancia_estimada_km / velocidad_kmh) * 60))
    tiempo=datetime.now(timezone.utc)
    logger.info("[trace_id=%s]|Calculo exitoso.|Distancia estimada km =%.2f|ETA min=%d|Tiempo de calculo = %s|Fuente = Local",trace_id,distancia_estimada_km,eta_minutos,tiempo)
    return ResultadoEstimacionRuta(
        distancia_estimada_km=distancia_estimada_km,
        eta_minutos=eta_minutos,
        calculado_en=tiempo,
        fuente=FuenteInfo.ESTIMACION_LOCAL,)
