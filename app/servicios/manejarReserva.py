from uuid import UUID
from datetime import datetime, timezone, timedelta
from app.modelos.cache_models import CacheResTemp
from app.esquemas.esquemas import CambioReservaTemporal, ResultadoReservaTemporal, EstadoTmp
from app.errores.exceptionsSemanticos import RecursoNoDisponible,ErrorConflicto,DependenciaNoDisponible
import logging
from redis_om import NotFoundError

logger = logging.getLogger(__name__)

TTL_RESERVA_SEGUNDOS = 600  # 10 minutos

class ReservaService:
    @staticmethod
    def _obtener_reserva(conductor_id: UUID, trace_id: str) -> CacheResTemp | None:
        clave_redis = str(conductor_id)
        try:
            return CacheResTemp.get(clave_redis)
        except NotFoundError:
            logger.debug("[trace_id=%s]|Sin reserva activa en Redis para conductor_id=%s",trace_id,conductor_id,)
            return None
        except Exception as exc:
            logger.exception("[trace_id=%s]|Error al consultar reserva en Redis|conductor_id=%s|Tipo=%s|Detalle=%s",
                trace_id,conductor_id,type(exc).__name__,exc,)
            raise DependenciaNoDisponible(detail="No se pudo consultar el caché.",retry_after=1) from exc

    @staticmethod
    def _persistir_con_ttl(registro: CacheResTemp, trace_id: str) -> None:
        try:
            registro.save()
            registro.expire(TTL_RESERVA_SEGUNDOS)
        except Exception as exc:
            logger.exception(
                "[trace_id=%s]|Error al guardar/aplicar TTL de reserva en Redis|conductor_id=%s|Tipo=%s|Detalle=%s",
                trace_id,registro.conductor_id,type(exc).__name__,exc,)
            raise DependenciaNoDisponible(
                detail="No se pudo resguardar datos.") from exc
    
    @staticmethod
    def cambiar_reserva(conductor_id: UUID,datos: CambioReservaTemporal,trace_id: str,) -> tuple[ResultadoReservaTemporal, bool]:
        ahora = datetime.now(timezone.utc)
        reserva_existente = ReservaService._obtener_reserva(conductor_id, trace_id)#obtenemos el registro cache/o no
        # CASO A: RESERVADO
        if datos.estado_temporal == EstadoTmp.RESERVADO:
            if reserva_existente is not None:#si existe registro en cache
                if str(reserva_existente.solicitud_id) != str(datos.solicitud_id):#si la solicitud resguardado es distinto al body entrada
                    logger.warning(
                        "[trace_id=%s]|Conflicto de reserva|conductor_id=%s|solicitud_actual=%s|solicitud_entrante=%s",
                        trace_id,conductor_id,reserva_existente.solicitud_id,datos.solicitud_id,)
                    raise ErrorConflicto(title="Conductor no disponible para reserva",
                        detail="El conductor ya está reservado por otra solicitud.",code="CONDUCTOR_RESERVADO",)

                if reserva_existente.estado_temporal == EstadoTmp.RESERVADO:
                    logger.info("[trace_id=%s]|Reserva ya activa para misma solicitud|conductor_id=%s|solicitud_id=%s",
                        trace_id,conductor_id,datos.solicitud_id,)
                    return (
                        ResultadoReservaTemporal(
                            conductor_id=reserva_existente.conductor_id,
                            solicitud_id=reserva_existente.solicitud_id,
                            estado_temporal=EstadoTmp.RESERVADO,
                            actualizado_en=reserva_existente.actualizado_en,
                            expira_en=reserva_existente.expira_en,
                            idempotente=True,)
                        ,False,) #se realizo actividad idempotente. HTTP 200
                #Viene LIBERADO, pero para LIBERAR debio estar en RESERVADO, o sea que no podemos arrepentirnos de liberar un conductor
                logger.warning("[trace_id=%s]|Intento de reabrir reserva ya liberada|conductor_id=%s|solicitud_id=%s",
                    trace_id,conductor_id,datos.solicitud_id,)
                raise ErrorConflicto(title="Reserva ya Liberada",
                                    detail="La reserva para esta solicitud ya fue liberada y no puede reabrirse.",
                                    code="RESERVA_YA_LIBERADA",)
            #no existe reserva en cache
            expiracion = ahora + timedelta(seconds=TTL_RESERVA_SEGUNDOS)
            nueva_reserva = CacheResTemp(
                pk=str(conductor_id),
                conductor_id=conductor_id,
                solicitud_id=datos.solicitud_id,
                estado_temporal=EstadoTmp.RESERVADO,
                actualizado_en=ahora,
                expira_en=expiracion,)
            ReservaService._persistir_con_ttl(nueva_reserva, trace_id)

            resultado = ResultadoReservaTemporal(
                conductor_id=conductor_id,
                solicitud_id=datos.solicitud_id,
                estado_temporal=EstadoTmp.RESERVADO,
                actualizado_en=ahora,
                expira_en=expiracion,
                idempotente=False,)
            logger.info("[trace_id=%s]|Reserva temporal creada|conductor_id=%s|solicitud_id=%s|expira_en=%s",
                trace_id,conductor_id,datos.solicitud_id,expiracion.isoformat(),)
            return resultado, True  # HTTP 201

        # CASO B: LIBERADO
        if reserva_existente is None:
            logger.warning("[trace_id=%s]|Intento de liberar reserva inexistente|conductor_id=%s|solicitud_id=%s",
                trace_id,conductor_id,datos.solicitud_id,)
            raise RecursoNoDisponible(title="Reserva no encontrada",
                detail="No existe una reserva para la combinación de conductor_id y solicitud_id indicada.",
                code="RESERVA_NO_ENCONTRADA",)

        if str(reserva_existente.solicitud_id) != str(datos.solicitud_id):
            logger.warning("[trace_id=%s]|Solicitud no coincide al liberar reserva|conductor_id=%s|solicitud_reserva=%s|solicitud_entrante=%s",
                trace_id,conductor_id,reserva_existente.solicitud_id,datos.solicitud_id,)
            raise ErrorConflicto(title="Conflicto al liberar reserva",detail="La solicitud_id no coincide con la reserva del conductor.",
                code="SOLICITUD_NO_COINCIDE",)

        if reserva_existente.estado_temporal == EstadoTmp.LIBERADO:
            logger.info("[trace_id=%s]|Liberación repetida de reserva ya liberada|conductor_id=%s|solicitud_id=%s",
                trace_id,conductor_id,datos.solicitud_id,)
            return (ResultadoReservaTemporal(
                    conductor_id=conductor_id,
                    solicitud_id=datos.solicitud_id,
                    estado_temporal=EstadoTmp.LIBERADO,
                    actualizado_en=reserva_existente.actualizado_en,
                    expira_en=reserva_existente.expira_en,
                    idempotente=True,)
                ,False,)# HTTP 200

        reserva_existente.estado_temporal = EstadoTmp.LIBERADO
        reserva_existente.actualizado_en = ahora
        ReservaService._persistir_con_ttl(reserva_existente, trace_id)

        resultado = ResultadoReservaTemporal(
            conductor_id=conductor_id,
            solicitud_id=datos.solicitud_id,
            estado_temporal=EstadoTmp.LIBERADO,
            actualizado_en=ahora,
            expira_en=reserva_existente.expira_en,
            idempotente=False,)
        logger.info("[trace_id=%s]|Reserva liberada|conductor_id=%s|solicitud_id=%s",trace_id,conductor_id,datos.solicitud_id,)
        return resultado, False  # HTTP 200
