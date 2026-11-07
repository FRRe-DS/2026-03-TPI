from uuid import UUID
from datetime import datetime
from fastapi import HTTPException, status
from redis_om.model import NotFoundError
from app.modelos.cache_models import UbicacionesCond  
from app.esquemas.esquemas import ActualizarUbicacion, UbicacionRegistrada, Coordenada 
from ..errores.exceptionsSemanticos import ErrorTimeStamp

class ActualizarUbicacionService:
    @staticmethod
    def procesar(conductor_id: UUID, datos: ActualizarUbicacion) -> tuple[UbicacionRegistrada, bool]:
        """
        Verifica si el conductor se encuentra en Redis.
        - Si está: realiza la actualización validando reglas de negocio. (es_nuevo = False -> 200)
        - Si no está: realiza su creación efímera con TTL. (es_nuevo = True -> 201)
        """
        ubicacion_existente = None
        # 1. Comprobar si se encuentra en Redis
        try:
            ubicacion_existente = UbicacionesCond.get(str(conductor_id))
        except NotFoundError:
            ubicacion_existente = None
        if ubicacion_existente:
            # --- FLUJO DE ACTUALIZACIÓN ---
            
            # Validación de regla de negocio: Timestamp anterior al vigente
            if datos.timestamp_ubicacion < ubicacion_existente.timestamp_ubicacion:
                raise ErrorTimeStamp(detail="El timestamp de la ubicación es anterior a la vigente.")

            # Validación de regla de negocio: Mismo timestamp con coordenadas distintas
            if datos.timestamp_ubicacion == ubicacion_existente.timestamp_ubicacion:
                if (datos.latitud != ubicacion_existente.geo.latitud) or (datos.longitud != ubicacion_existente.geo.longitud):
                    raise ErrorTimeStamp()
            # Actualizamos los campos en el objeto de Redis
            ubicacion_existente.geo = Coordenada(latitud=datos.latitud, longitud=datos.longitud)
            ubicacion_existente.timestamp_ubicacion = datos.timestamp_ubicacion
            ubicacion_existente.save()
            # Refrescamos el TTL de 30 segundos
            try:
                ubicacion_existente.expire(30)
            except Exception:
                pass
            # Calculamos la expiración (ahora + 30 segundos) alineado al TTL de Redis
            tiempo_actual_utc = datetime.now(timezone.utc)
            expiracion_calculada = tiempo_actual_utc + timedelta(seconds=30)
            resultado = UbicacionRegistrada(
                conductor_id=conductor_id,
                timestamp_ubicacion=datos.timestamp_ubicacion,
                recibida_en=datetime.utcnow(),
                vigente=True,
                expira_en=expiracion_calculada
            )
            return resultado, False  # False indica que fue una actualización (200 OK)
        else:
            # --- FLUJO DE CREACIÓN ---
            nueva_geo = Coordenada(latitud=datos.latitud, longitud=datos.longitud)
            nueva_ubicacion = UbicacionesCond(
                pk=str(conductor_id),
                conductor_id=conductor_id,
                geo=nueva_geo,
                timestamp_ubicacion=datos.timestamp_ubicacion
            )
            nueva_ubicacion.save()
            # Aplicamos el TTL de 30 segundos exigido por la arquitectura efímera
            try:
                nueva_ubicacion.expire(30)
            except Exception:
                pass
            tiempo_actual_utc = datetime.now(timezone.utc)
            expiracion_calculada = tiempo_actual_utc + timedelta(seconds=30)
            resultado = UbicacionRegistrada(
                conductor_id=conductor_id,
                timestamp_ubicacion=datos.timestamp_ubicacion,
                recibida_en=datetime.utcnow(),
                vigente=True,
                expira_en=expiracion_calculada
            )
            return resultado, True  # True indica que fue una creación (201 Created)