from datetime import datetime, timezone
from typing import List
from uuid import UUID
from geopy.distance import geodesic
import logging
from app.modelos.cache_models import UbicacionesCond, CacheEstOp, CacheResTemp
from app.esquemas.esquemas import QueryCercanos, ResultadoBusquedaConductores, Candidatos, VehiculosSoportados
from app.errores.exceptionsSemanticos import DependenciaNoDisponible
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
from redis_om.model.model import NotFoundError

logger=logging.getLogger(__name__)
# Radios progresivos según contrato: inicia en 5 km, amplía en +1.5 km hasta máx 9.5 km
RADIOS_PROGRESIVOS = [5.0, 6.5, 8.0, 9.5]

def _mock_verificar_habilitacion_m3(conductor_id: UUID, tipo_vehiculo: VehiculosSoportados) -> bool:
    """
    PUNTO DE INTEGRACIÓN SINCRÓNICA CON M3 (MOCK / SIMULACIÓN)
    Cuando M3 esté disponible, debe verificar que el conductor tenga estado APPROVED
    y el tipo de vehículo habilitado. Si M3 falla, se debe lanzar excepción para
    que el llamador descarte al candidato (no devolver candidatos sin validar).
    """
    return True

class CandidatosCercanos:
    @staticmethod
    def buscar(query: QueryCercanos,trace_id:str) -> ResultadoBusquedaConductores:
        logger.info("[trace_id=%s]|Inicio de busqueda cercana de candidatos.",trace_id)
        try:
            todas_ubicaciones = UbicacionesCond.find().all()
        except Exception as e:
            # Redis no disponible → 503, no silenciar el fallo devolviendo lista vacía
            logger.exception("[trace_id=%s]|Error al intentar acceder a la redis|Tipo = %s|Detalle = %s",trace_id,type(e).__name__,e)
            raise DependenciaNoDisponible(
                detail="No se pudo acceder al almacén de ubicaciones (Redis). Intente nuevamente en unos instantes."
            ) from e

        candidatos_finales: List[Candidatos] = []
        # radio_aplicado por defecto al máximo (si no hay candidatos en ningún radio)
        radio_aplicado = RADIOS_PROGRESIVOS[-1]

        # Búsqueda progresiva: se detiene al primer radio que devuelva candidatos
        for radio_km in RADIOS_PROGRESIVOS:
            candidatos_radio: List[Candidatos] = []

            for ubicacion in todas_ubicaciones:
                conductor_id = ubicacion.conductor_id
                lat_cond = ubicacion.geo.latitud
                lon_cond = ubicacion.geo.longitud

                # Calcular distancia en línea recta con geopy
                punto_origen = (query.origen_latitud, query.origen_longitud)
                punto_conductor = (lat_cond, lon_cond)
                distancia_km = geodesic(punto_origen, punto_conductor).kilometers

                if distancia_km > radio_km:
                    logger.debug("[trace_id=%s]|Candidato encontrado pero fuera del radio de busqueda",trace_id)
                    continue  # fuera del radio actual, descartar

                # Validar connected y available desde cache propio (M4)
                try:
                    estado_op = CacheEstOp.get(str(conductor_id))
                    connected = getattr(estado_op, 'connected', False)
                    available = getattr(estado_op, 'available', False)
                    if not estado_op or not connected or not available:
                        logger.debug("[trace_id=%s]|Candidato encontrado pero no cumple la regla de negocio de disponibilidad",trace_id)
                        continue
                except NotFoundError:#TODO: es cuestionable ya que se supone que se pregunta despues y M3 actualiza la tabla
                    continue  # sin registro de estado operativo → no es candidato, Redis está vivo
                except (RedisConnectionError, RedisTimeoutError) as e:
                    logger.exception("[trace_id=%s]|Error de redis|Tipo= %s|Detalle= %s",trace_id,type(e).__name__,e)
                    raise DependenciaNoDisponible(
                        detail="No se pudo acceder a el estado operativo del conductor (Redis no disponible)."
                    ) from e
                except Exception as e:
                    logger.exception("[trace_id=%s]|Error de inesperado de datos|Tipo= %s|Detalle= %s",trace_id,type(e).__name__,e)
                    continue  # dato corrupto u otro error puntual → descartar este candidato

                # Verificar que no tenga reserva temporal activa
                try: #TODO: Esto puede cambiar por contrato nuevo, verificar. 
                    reserva = CacheResTemp.get(str(conductor_id))
                    if reserva:
                        if reserva.estado_temporal == "RESERVADO":
                            logger.debug("[trace_id=%s]|Estado temporal %s impide candidatura|Conductor id =%s",trace_id,reserva.estado_temporal,conductor_id)
                            continue  # reservado en otra solicitud, descartar
                        else:
                            logger.debug("[trace_id=%s]|Estado temporal %s permite candidatura|Conductor id =%s",trace_id,reserva.estado_temporal,conductor_id)
                    else:
                        logger.debug("[trace_id=%s]|Estado temporal no existe|Conductor id =%s",trace_id,conductor_id)
                except (RedisConnectionError, RedisTimeoutError) as e:
                    logger.exception("[trace_id=%s]|No se pudo acceder a registro de reservas|Tipo= %s|Detalle= %s",trace_id,type(e).__name__,e)
                    raise DependenciaNoDisponible(detail="No se pudo acceder a el registro de reservas(Redis no disponible).") from e
                #TODO: tiene ttl la tabla de reservas de la redis asi que este exeption estaria de mas, verificar
                except Exception as e:
                    logger.exception("[trace_id=%s]|No se pudo acceder a registro de reservas|Tipo= %s|Detalle= %s",trace_id,type(e).__name__,e)
                    continue  # no se pudo acceder a reserva, descartar (no devolver sin validar)

                # Verificar habilitación con M3 (APPROVED + vehículo habilitado)
                # Si M3 falla, se descarta el candidato: M4 no devuelve candidatos sin validar
                try:
                    if not _mock_verificar_habilitacion_m3(conductor_id, query.tipo_vehiculo):
                        logger.debug("[trace_id=%s]|Candidato no habilidato por respuesta sincronica de M3, descartando|Conductor id = %s",trace_id,conductor_id)
                        continue
                except Exception as e:
                    logger.exception("[trace_id=%s]|Error de respuesta ante el modulo sincronico M3|Tipo= %s|Detalle = %s",trace_id,type(e).__name__,e)
                    continue  # M3 no disponible → descartar según contrato

                # Candidato válido: construir objeto con ETA estimado (~3 min/km)
                eta_estimado = max(1, round(distancia_km * 3))
                candidato = Candidatos(
                    conductor_id=conductor_id,
                    distancia_origen_km=round(distancia_km, 2),
                    eta_retiro_minutos=eta_estimado,
                    tipo_vehiculo=query.tipo_vehiculo
                )
                candidatos_radio.append(candidato)

            if candidatos_radio: 
                """
                Si hay un solo candidato en cierto radio, se detiene la busqueda progresiva y 
                solo se devuelve un candidato por lo que si se rechaza ese conductor se queda 
                sin candidatos de radio mas lejanos
                """
                # Encontramos candidatos en este radio, detenemos la búsqueda progresiva
                candidatos_finales = candidatos_radio
                radio_aplicado = radio_km
                break
            # Sin candidatos en este radio → continuar con el siguiente (más amplio)

        # Ordenar por distancia ascendente (el más cercano primero)
        candidatos_finales.sort(key=lambda x: x.distancia_origen_km)

        # Aplicar límite si fue especificado
        if query.limite:
            candidatos_finales = candidatos_finales[:query.limite]
        if candidatos_finales:
            logger.info("[trace_id=%s]|Se encontraron candidatos.|Cantidad = %d",trace_id,len(candidatos_finales))
        else:
            logger.info("[trace_id=%s]|No see encontraron candidatos.|Se devuelve conductores vacio",trace_id)
        
        return ResultadoBusquedaConductores(
            conductores=candidatos_finales,
            radio_aplicado_km=radio_aplicado,
            generado_en=datetime.now(timezone.utc))
