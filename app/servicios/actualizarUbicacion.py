from uuid import UUID
from datetime import datetime, timezone, timedelta
from redis_om.model import NotFoundError
from app.modelos.cache_models import UbicacionesCond  
from app.esquemas.esquemas import ActualizarUbicacion, UbicacionRegistrada, Coordenada 
from app.errores.exceptionsSemanticos import ErrorTimeStamp,DependenciaNoDisponible
import logging

logger = logging.getLogger(__name__)

class ActualizarUbicacionService:
    @staticmethod
    def procesar(conductor_id: UUID, datos: ActualizarUbicacion, trace_id: str) -> tuple[UbicacionRegistrada, bool]:
        """
        Verifica si el conductor se encuentra en Redis.
        - Si está: realiza la actualización validando reglas de negocio. (es_nuevo = False -> 200)
        - Si no está: realiza su creación efímera con TTL. (es_nuevo = True -> 201)
        """
        logger.info("[trace_id=%s]|Inicio endpoint actualizar ubicacion.",trace_id)
        ubicacion_existente = None
        # 1. Comprobar si se encuentra en Redis
        try:
            ubicacion_existente = UbicacionesCond.get(str(conductor_id))
        except NotFoundError:
            logger.debug("[trace_id=%s]|Conductor no posee registro en Redis:conductor_id %s",trace_id,conductor_id)
            ubicacion_existente = None
        except Exception as exc:
            logger.exception("[trace_id=%s]|Error al acceder a Redis para conductor conductor_id: %s",trace_id, conductor_id,)
            raise DependenciaNoDisponible(detail="Error al acceder a los datos de caché.",retry_after=1) from exc

        if ubicacion_existente:
            # --- FLUJO DE ACTUALIZACIÓN ---
            # Validación de regla de negocio: Timestamp anterior al vigente
            if datos.timestamp_ubicacion < ubicacion_existente.timestamp_ubicacion:
                logger.warning("[trace_id=%s]|Error por Conflicto de TimeStamps desfasados.|conductor id:%s",trace_id,conductor_id,)
                raise ErrorTimeStamp()

            # Validación de regla de negocio: Mismo timestamp con coordenadas distintas
            if datos.timestamp_ubicacion == ubicacion_existente.timestamp_ubicacion:
                if (datos.latitud != ubicacion_existente.geo.latitud) or (datos.longitud != ubicacion_existente.geo.longitud):
                    logger.warning("[trace_id=%s]|Error por Conflicto de TimeStamps iguales.|conductor id:%s",trace_id,conductor_id,)
                    raise ErrorTimeStamp()
            # Actualizamos los campos en el objeto de Redis
            ubicacion_existente.geo = Coordenada(latitud=datos.latitud, longitud=datos.longitud)
            ubicacion_existente.timestamp_ubicacion = datos.timestamp_ubicacion

            try:
                ubicacion_existente.save()
                #refrescamos el ttl
                ubicacion_existente.expire(30)
            except Exception as exc:
                logger.exception("[trace_id=%s]|Error al intentar actualizar el registro en la redis.|conductor id:%s",trace_id,conductor_id,)
                raise DependenciaNoDisponible(detail="Error al intentar operaracion",retry_after=1) from exc
            # Calculamos la expiración (ahora + 30 segundos) alineado al TTL de Redis
            tiempo_actual_utc = datetime.now(timezone.utc)
            expiracion_calculada = tiempo_actual_utc + timedelta(seconds=30)
            resultado = UbicacionRegistrada(
                conductor_id=conductor_id,
                timestamp_ubicacion=datos.timestamp_ubicacion,
                recibida_en=datetime.now(timezone.utc),
                vigente=True,
                expira_en=expiracion_calculada
            )
            logger.info("[trace_id=%s]|Actualizacion exitosa en redis.|respuesta: %s ",trace_id,resultado,)
            return resultado, False  # False indica que fue una actualización (200 OK)
        else:
            # --- FLUJO DE CREACIÓN ---
            nueva_geo = Coordenada(latitud=datos.latitud, longitud=datos.longitud)
            nueva_ubicacion = UbicacionesCond(
                pk=str(conductor_id),
                conductor_id=conductor_id,
                geo=nueva_geo,
                timestamp_ubicacion=datos.timestamp_ubicacion)
            
            try:
                nueva_ubicacion.save()
                # Aplicamos el TTL de 30 segundos exigido por la arquitectura efímera
                nueva_ubicacion.expire(30)
            except Exception as exc:
                logger.exception("[trace_id=%s]|Error al intentar registrar en la redis.|conductor id:%s ",trace_id,conductor_id,)
                raise DependenciaNoDisponible(detail="Error al intentar operaracion",retry_after=1) from exc
            
            tiempo_actual_utc = datetime.now(timezone.utc)
            expiracion_calculada = tiempo_actual_utc + timedelta(seconds=30)
            resultado = UbicacionRegistrada(
                conductor_id=conductor_id,
                timestamp_ubicacion=datos.timestamp_ubicacion,
                recibida_en=datetime.now(timezone.utc),
                vigente=True,
                expira_en=expiracion_calculada)
            logger.info("[trace_id=%s]|Registro exitoso de redis.|respuesta: %s  ",trace_id,resultado,)
            return resultado, True  # True indica que fue una creación (201 Created)
