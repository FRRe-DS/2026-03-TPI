#def RegistrarReserva():
    #pass

from uuid import UUID
from datetime import datetime, timezone, timedelta
from app.modelos.cache_models import CacheResTemp, UbicacionesCond
from app.esquemas.esquemas import CambioReservaTemporal, ResultadoReservaTemporal, EstadoTmp, Coordenada
from app.errores.exceptionsSemanticos import ProblemaDominio

class ReservaService:
    @staticmethod
    def cambiar_reserva(conductor_id: UUID, datos: CambioReservaTemporal) -> tuple[ResultadoReservaTemporal, bool]:
        clave_redis = str(conductor_id)
        ahora = datetime.now(timezone.utc)
        
        # 1. Buscar si ya existe una reserva activa para este chofer en Redis
        reserva_existente = None
        try:
            reserva_existente = CacheResTemp.get(clave_redis)
        except Exception:
            reserva_existente = None

        # -------------------------------------------------------------
        # CASO A: PETICIÓN DE NUEVA RESERVA ("RESERVADO")
        # -------------------------------------------------------------
        if datos.estado_temporal == EstadoTmp.RESERVADO:
            # Si el chofer ya está reservado por OTRA solicitud distinta -> Conflicto (409)
            if reserva_existente and reserva_existente.estado_temporal == EstadoTmp.RESERVADO:
                if str(reserva_existente.solicitud_id) != str(datos.solicitud_id):
                    raise ProblemaDominio(
                        title="Conductor no disponible para reserva",
                        status_code=409,
                        detail="El conductor ya está reservado por otra solicitud.",
                        code="CONDUCTOR_RESERVADO"
                    )
            
            # Obtenemos la última ubicación registrada del chofer para la foto de la reserva
            ubicacion_actual = None
            try:
                ubicacion_actual = UbicacionesCond.get(clave_redis)
            except Exception:
                pass
            
            coordenada_default = Coordenada(latitud=0.0, longitud=0.0)
            geo = ubicacion_actual.geo if ubicacion_actual else coordenada_default

            # Calculamos los 10 minutos de expiración
            expiracion = ahora + timedelta(minutes=10)

            # Guardamos la reserva en Redis
            nueva_reserva = CacheResTemp(
                pk=clave_redis,
                conductor_id=conductor_id,
                solicitud_id=datos.solicitud_id,
                estado_temporal=EstadoTmp.RESERVADO,
                origen=geo,
                destino=geo,
                actualizado_en=ahora
            )
            nueva_reserva.save()

            # Aplicamos el TTL de 10 minutos (600 segundos) en Redis (RNF-03 y RNF-11)
            try:
                nueva_reserva.expire(600)
            except Exception:
                pass

            resultado = ResultadoReservaTemporal(
                conductor_id=conductor_id,
                solicitud_id=datos.solicitud_id,
                estado_temporal=EstadoTmp.RESERVADO,
                actualizado_en=ahora,
                expira_en=expiracion,
                idempotente=False
            )
            return resultado, True  # True indica que fue creación nueva (HTTP 201)

        # -------------------------------------------------------------
        # CASO B: FINALIZAR RESERVA ("OFERTA_ACEPTADA" u "OFERTA_RECHAZADA")
        # -------------------------------------------------------------
        else:
            # Si se intenta finalizar pero no había ninguna reserva previa en Redis -> 404
            if not reserva_existente:
                raise ProblemaDominio(
                    title="Reserva no encontrada",
                    status_code=404,
                    detail="No existe una reserva activa para este conductor.",
                    code="RESERVA_NO_ENCONTRADA"
                )

            # Si la solicitud_id no coincide con la que lo tenía reservado -> 409
            if str(reserva_existente.solicitud_id) != str(datos.solicitud_id):
                raise ProblemaDominio(
                    title="Conflicto de solicitud",
                    status_code=409,
                    detail="La solicitud_id no coincide con la reserva activa.",
                    code="SOLICITUD_NO_COINCIDE"
                )

            # Si la oferta fue RECHAZADA: borramos la reserva de Redis para que el chofer quede libre de inmediato
            if datos.estado_temporal == EstadoTmp.OFERTA_RECHAZADA:
                try:
                    CacheResTemp.delete(clave_redis)
                except Exception:
                    pass
            else:
                # Si fue ACEPTADA: actualizamos el estado
                reserva_existente.estado_temporal = datos.estado_temporal
                reserva_existente.actualizado_en = ahora
                reserva_existente.save()

            resultado = ResultadoReservaTemporal(
                conductor_id=conductor_id,
                solicitud_id=datos.solicitud_id,
                estado_temporal=datos.estado_temporal,
                actualizado_en=ahora,
                expira_en=None,
                idempotente=False
            )
            return resultado, False  # False indica que fue actualización (HTTP 200)