from datetime import datetime, timezone
import logging
from uuid import UUID
from redis_om import NotFoundError
from app.modelos.cache_models import CacheEstOp
from app.esquemas.esquemas import EstadoOperativo, EstadoOperativoRegistrado
from app.errores.exceptionsSemanticos import DependenciaNoDisponible,ErrorEvento_id,ErrorTimeStamp

logger = logging.getLogger(__name__)

class ServicioEstadoOperativo:

    @staticmethod
    def _obtener_estado_actual(conductor_id: UUID, trace_id: str) -> CacheEstOp | None:
        try:
            return CacheEstOp.get(str(conductor_id))
        except NotFoundError:
            logger.info(
                "[trace_id=%s]|No existe estado operativo previo para conductor_id=%s",trace_id,conductor_id,)
            return None
        except Exception as exc:
            logger.exception("[trace_id=%s]|Error al consultar estado operativo en Redis para conductor_id=%s|Tipo=%s|Detalle=%s",
                trace_id,conductor_id,type(exc).__name__,exc,)
            raise DependenciaNoDisponible(detail="No se pudo consultar el estado operativo en Redis.",retry_after=1) from exc

    @staticmethod
    def _validar_orden_y_duplicados(actual: CacheEstOp | None,body: EstadoOperativo,conductor_id: UUID,trace_id: str,) -> None:
        #si no recuperamos nada de la redis devolvemos.
        if actual is None:
            return

        event_id_entrante = str(body.event_id) if body.event_id is not None else None
        if event_id_entrante and actual.event_id and event_id_entrante == actual.event_id:
            logger.warning("[trace_id=%s]|Evento duplicado detectado|conductor_id=%s|event_id=%s",trace_id,conductor_id,event_id_entrante,)
            raise ErrorEvento_id(detail="El evento ya fue procesado para el conductor.")

        if actual.timestamp_evento is not None and body.timestamp_evento is not None:
            ts_entrante = body.timestamp_evento
            ts_actual = actual.timestamp_evento

            # Normalizamos a UTC si alguno viene naive para evitar TypeError al comparar
            if isinstance(ts_actual, str):
                ts_actual = datetime.fromisoformat(ts_actual)
            if isinstance(ts_entrante, str):
                ts_entrante = datetime.fromisoformat(ts_entrante)

            # Normalizamos a UTC si alguno viene naive para evitar TypeError al comparar
            if ts_entrante.tzinfo is None:
                ts_entrante = ts_entrante.replace(tzinfo=timezone.utc)
            if ts_actual.tzinfo is None:
                ts_actual = ts_actual.replace(tzinfo=timezone.utc)

            if ts_entrante < ts_actual:
                logger.warning("[trace_id=%s]|Conflicto de timestamp (evento atrasado)|conductor_id=%s|entrante=%s|actual=%s",
                    trace_id,conductor_id,ts_entrante.isoformat(),ts_actual.isoformat(),)
                raise ErrorTimeStamp()

    @staticmethod
    def actualizar_estado(conductor_id: UUID,body: EstadoOperativo,trace_id: str,) -> tuple[EstadoOperativoRegistrado, bool]:
        logger.debug("[trace_id=%s]|Entrada a metodo actualizar_estado",trace_id)
        recibido_en = datetime.now(timezone.utc)
        actual = ServicioEstadoOperativo._obtener_estado_actual(conductor_id, trace_id)
        # Obtenemos confirmación para distinguir 201 (nuevo) de 200 (actualizado)
        es_nuevo = actual is None
        ServicioEstadoOperativo._validar_orden_y_duplicados(actual, body, conductor_id, trace_id)

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
            raise DependenciaNoDisponible(detail="No se pudo guardar el estado operativo en Redis.",retry_after=1) from exc

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
