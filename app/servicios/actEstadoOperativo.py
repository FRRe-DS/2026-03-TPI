from datetime import datetime, timezone
import logging
from uuid import UUID
from redis_om import NotFoundError
from app.modelos.cache_models import CacheEstOp
from app.esquemas.esquemas import EstadoOperativo, EstadoOperativoRegistrado
from app.errores.exceptionsSemanticos import DependenciaNoDisponible

logger = logging.getLogger(__name__)

class ServicioEstadoOperativo:

    @staticmethod
    def _existe_estado(conductor_id: UUID, trace_id: str) -> bool:
        try:
            CacheEstOp.get(str(conductor_id))
            return True
        except NotFoundError:
            logger.info("[trace_id=%s]|No existe estado operativo previo para conductor_id=%s",trace_id,conductor_id,)
            return False
        except Exception as exc:
            logger.exception("[trace_id=%s]|Error al consultar estado operativo en Redis para conductor_id=%s|Tipo %s|Detalle %s",trace_id,conductor_id,type(exc).__name__,exc)
            raise DependenciaNoDisponible(detail="No se pudo consultar el estado operativo en Redis.") from exc

    @staticmethod
    def actualizar_estado(conductor_id: UUID,body: EstadoOperativo,trace_id: str,) -> tuple[EstadoOperativoRegistrado, bool]:
        logger.debug("[trace_id=%s]|Entrada a metodo actualizar_estado",trace_id)
        recibido_en = datetime.now(timezone.utc)
        # Obtenemos confirmación para distinguir 201 (nuevo) de 200 (actualizado)
        es_nuevo = not ServicioEstadoOperativo._existe_estado(conductor_id,trace_id)
        # Regla de negocio: si no está conectado, no puede estar disponible
        if not body.connected:
            available_efectivo = False
            logger.debug("[trace_id=%s]|Conductor desconectado (connected=False); se fuerza available=False para conductor_id=%s",trace_id,conductor_id,)
        else:
            available_efectivo = body.available

        # Reasignación de datos para persistir en Redis
        registro = CacheEstOp(
            pk=str(conductor_id),
            conductor_id=conductor_id,
            event_id=str(body.event_id) if body.event_id is not None else None,
            connected=body.connected,
            available=available_efectivo,
            actualizado_en=body.timestamp_evento,
            recibido_en=recibido_en,
        )

        # Guardamos/actualizamos estado capturando fallos de conexión/operación en Redis
        try:
            registro.save()
        except Exception as exc:
            logger.exception("[trace_id=%s]|Fallo al guardar estado operativo en Redis para conductor_id=%s ",trace_id,conductor_id,)
            raise DependenciaNoDisponible(detail="No se pudo guardar el estado operativo en Redis.") from exc

        # Formalizamos la respuesta a retornar
        respuesta = EstadoOperativoRegistrado(
            conductor_id=conductor_id,
            event_id=body.event_id,
            connected=body.connected,
            available=available_efectivo,
            actualizado_en=body.timestamp_evento,
            recibido_en=recibido_en,)
        
        logger.info("[trace_id=%s]|Estado operativo actualizado|respuesta %s ",trace_id,respuesta,)
        return respuesta, es_nuevo