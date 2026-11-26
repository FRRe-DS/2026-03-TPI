#TODO: para los test unitarios o de integracion parcial, hacer mock del consumo M3.
#TODO: para los test de integracion docker, tener en cuenta las direcciones internas del contenedor en el entorno, asi como las url,realms,networks, nombres de contenedores.
from datetime import datetime, timezone
from typing import List
from uuid import UUID
from geopy.distance import geodesic
import logging, httpx, os, time
from app.modelos.cache_models import UbicacionesCond, CacheEstOp, CacheResTemp
from app.esquemas.esquemas import QueryCercanos, ResultadoBusquedaConductores, Candidatos, VehiculosSoportados, EstadoTmp
from app.errores.exceptionsSemanticos import DependenciaNoDisponible
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
from redis_om.model.model import NotFoundError

logger=logging.getLogger(__name__)
# Radios progresivos según contrato: inicia en 5 km, amplía en +1.5 km hasta máx 9.5 km
RADIOS_PROGRESIVOS = [5.0, 6.5, 8.0, 9.5]

M3_BASE_URL = os.getenv("M3_BASE_URL", "http://localhost:8080/api/v1").rstrip("/")
M3_TIMEOUT_SECONDS = float(os.getenv("M3_TIMEOUT_SECONDS", "1.5"))
KEYCLOAK_TOKEN_URL = os.getenv("KEYCLOAK_TOKEN_URL","http://localhost:8080/realms/ds-2026-realm/protocol/openid-connect/token",).strip()
M3_CLIENT_ID_ACTUAL = os.getenv("M3_KEYCLOAK_CLIENT_ID", "").strip()
if M3_CLIENT_ID_ACTUAL:
    if M3_CLIENT_ID_ACTUAL == os.getenv("M3_CLIENT_ID2","").strip():
        M3_SECRET_CLIENT_ACTUAL = os.getenv("G2_CLIENT_SECRET", "").strip()
    else:
        M3_SECRET_CLIENT_ACTUAL = os.getenv("G15_CLIENT_SECRET", "").strip()

M3_SERVICE_TOKEN = os.getenv("M3_SERVICE_TOKEN", "").strip()

_TOKEN_CACHE: dict[str, float | str | None] = {
    "token": M3_SERVICE_TOKEN or None,
    "expira_en": float("inf") if M3_SERVICE_TOKEN else 0.0,
}

def _obtener_token_m3() -> str:
    ahora = time.time()
    token_actual = _TOKEN_CACHE["token"]
    expira_en = float(_TOKEN_CACHE["expira_en"] or 0.0)

    if isinstance(token_actual, str) and token_actual and ahora < (expira_en - 15.0):
        return token_actual

    if KEYCLOAK_TOKEN_URL and M3_CLIENT_ID_ACTUAL and M3_SECRET_CLIENT_ACTUAL:
        resp = httpx.post(KEYCLOAK_TOKEN_URL,data={
                "grant_type": "client_credentials",
                "client_id": M3_CLIENT_ID_ACTUAL,
                "client_secret": M3_SECRET_CLIENT_ACTUAL,},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=M3_TIMEOUT_SECONDS,)
        resp.raise_for_status()
        payload = resp.json()
        nuevo_token = payload["access_token"]
        expires_in = float(payload.get("expires_in", 300))
        _TOKEN_CACHE["token"] = nuevo_token
        _TOKEN_CACHE["expira_en"] = ahora + expires_in
        return nuevo_token
    if isinstance(token_actual, str) and token_actual:
        return token_actual
    raise RuntimeError("Faltan M3_KEYCLOAK_CLIENT_ID / M3_KEYCLOAK_CLIENT_SECRET (o M3_SERVICE_TOKEN) en el entorno.")

def _construir_headers_m3() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = _obtener_token_m3()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _verificar_candidato_m3(client: httpx.Client,conductor_id: UUID,tipo_vehiculo_requerido: VehiculosSoportados,trace_id: str,) -> bool:
    
    """
    Valida de forma atómica contra M3
    1) Estado operativo == DISPONIBLE y vehículo activo presente.
    2) Vehículo activo con habilitación APROBADA y tipo coincidente con el requerido.
    Ante fallo de red, timeout o error de M3 en este candidato, registra en servidor y retorna False
    para descartar al candidato sin abortar toda la búsqueda.
    """
    try:
        # Paso 1: Verificar disponibilidad real del conductor
        resp_estado = client.get(f"/conductores/{conductor_id}/estado")
        if resp_estado.status_code == 404:
            logger.debug("[trace_id=%s]|Candidato no encontrado en M3 al consultar estado|conductor_id=%s",trace_id,conductor_id,)
            return False

        if resp_estado.status_code >= 400:
            logger.warning("[trace_id=%s]|Respuesta no exitosa de M3 en /estado|conductor_id=%s|status=%s|body=%s",
                trace_id,conductor_id,resp_estado.status_code,resp_estado.text[:200],)
            return False

        data_estado = resp_estado.json()
        estado_operativo = data_estado.get("estado")
        id_vehiculo_activo = data_estado.get("id_vehiculo_activo")

        if estado_operativo != "DISPONIBLE" or not id_vehiculo_activo:
            logger.debug("[trace_id=%s]|Candidato descartado por estado o sin vehículo activo en M3|conductor_id=%s|estado=%s|vehiculo_activo=%s",
                trace_id,conductor_id,estado_operativo,id_vehiculo_activo,)
            return False

        # Paso 2: Verificar que el vehículo activo sea adecuado y esté habilitado
        resp_vehiculo = client.get(f"/conductores/{conductor_id}/vehiculos/{id_vehiculo_activo}")
        if resp_vehiculo.status_code == 404:
            logger.debug("[trace_id=%s]|Vehículo activo no encontrado en M3|conductor_id=%s|vehiculo_id=%s",
                trace_id,conductor_id,id_vehiculo_activo,)
            return False

        if resp_vehiculo.status_code >= 400:
            logger.warning("[trace_id=%s]|Respuesta no exitosa de M3 en /vehiculos|conductor_id=%s|vehiculo_id=%s|status=%s|body=%s",
                trace_id,conductor_id,id_vehiculo_activo,resp_vehiculo.status_code,resp_vehiculo.text[:200],)
            return False

        data_vehiculo = resp_vehiculo.json()
        tipo_vehiculo_m3 = data_vehiculo.get("tipo")
        habilitacion_vehiculo = data_vehiculo.get("habilitacion")

        tipo_esperado = (tipo_vehiculo_requerido.value if hasattr(tipo_vehiculo_requerido, "value") else str(tipo_vehiculo_requerido))

        if tipo_vehiculo_m3 != tipo_esperado or habilitacion_vehiculo != "APROBADA":
            logger.debug("[trace_id=%s]|Vehículo no cumple tipo o habilitación en M3|conductor_id=%s|vehiculo_id=%s|tipo=%s (esperado=%s)|habilitacion=%s",
                trace_id,conductor_id,id_vehiculo_activo,tipo_vehiculo_m3,tipo_esperado,habilitacion_vehiculo,)
            return False

        logger.debug("[trace_id=%s]|Candidato validado en M3|conductor_id=%s|vehiculo_id=%s|tipo=%s",
            trace_id,conductor_id,id_vehiculo_activo,tipo_vehiculo_m3,)
        return True

    except httpx.TimeoutException as e:
        logger.warning("[trace_id=%s]|Timeout consultando M3 para candidato, se descarta|conductor_id=%s|detalle=%s",
            trace_id,conductor_id,e,)
        return False
    except httpx.HTTPError as e:
        logger.warning("[trace_id=%s]|Error de red/HTTP consultando M3 para candidato, se descarta|conductor_id=%s|tipo=%s|detalle=%s",
            trace_id,conductor_id,type(e).__name__,e,)
        return False
    except Exception as e:
        logger.exception("[trace_id=%s]|Error inesperado validando candidato en M3, se descarta|conductor_id=%s|tipo=%s|detalle=%s",
            trace_id,conductor_id,type(e).__name__,e,)
        return False

class CandidatosCercanos:
    @staticmethod
    def buscar(query: QueryCercanos,trace_id:str) -> ResultadoBusquedaConductores:
        logger.info("[trace_id=%s]|Inicio de busqueda cercana de candidatos.",trace_id)
        try:
            todas_ubicaciones = UbicacionesCond.find().all()
        except Exception as e:
            # Redis no disponible → 503, no silenciar el fallo devolviendo lista vacía
            logger.exception("[trace_id=%s]|Error al intentar acceder a la redis|Tipo = %s|Detalle = %s",trace_id,type(e).__name__,e)
            raise DependenciaNoDisponible(detail="No se pudo acceder al almacén de ubicaciones (Redis). Intente nuevamente en unos instantes."
            ,retry_after=1) from e

        candidatos_finales: List[Candidatos] = []
        # radio_aplicado por defecto al máximo (si no hay candidatos en ningún radio)
        radio_aplicado = RADIOS_PROGRESIVOS[-1]
        #preparamos headers y variables de timeout para consumir M3
        timeout = httpx.Timeout(M3_TIMEOUT_SECONDS)
        headers = _construir_headers_m3()

        with httpx.Client(base_url=M3_BASE_URL, headers=headers, timeout=timeout) as m3_client:
            for radio_km in RADIOS_PROGRESIVOS:
                candidatos_radio: List[Candidatos] = []
        
                for ubicacion in todas_ubicaciones:
                    conductor_id = ubicacion.conductor_id
                    lat_cond = ubicacion.geo.latitud
                    lon_cond = ubicacion.geo.longitud
        
                    punto_origen = (query.origen_latitud, query.origen_longitud)
                    punto_conductor = (lat_cond, lon_cond)
                    distancia_km = geodesic(punto_origen, punto_conductor).kilometers
        
                    if distancia_km > radio_km:
                        logger.debug("[trace_id=%s]|Candidato encontrado pero fuera del radio de busqueda|conductor_id=%s|distancia_km=%.2f|radio_km=%.2f",
                            trace_id,conductor_id,distancia_km,radio_km,)
                        continue
    
                    try:
                        estado_op = CacheEstOp.get(str(conductor_id))
                        connected = getattr(estado_op, "connected", False)
                        available = getattr(estado_op, "available", False)
                        if not estado_op or not connected or not available:
                            logger.debug("[trace_id=%s]|Candidato encontrado pero no cumple la regla de negocio de disponibilidad|conductor_id=%s",
                                trace_id,conductor_id,)
                            continue
                    #TODO:considerar que se puede consultar luego su estado operativo asi que esto estara de mas poner continue abajo
                    except NotFoundError:
                        logger.debug("[trace_id=%s]|Sin registro en CacheEstOp, se descarta candidato|conductor_id=%s",
                            trace_id,conductor_id,)
                    except (RedisConnectionError, RedisTimeoutError) as e:
                        logger.exception("[trace_id=%s]|Error de redis|Tipo= %s|Detalle= %s",trace_id,type(e).__name__,e,)
                        continue
                    except Exception as e:
                        logger.exception("[trace_id=%s]|Error inesperado de datos|Tipo= %s|Detalle= %s",
                            trace_id,type(e).__name__,e,)
                        continue
                    try:
                        reserva = CacheResTemp.get(str(conductor_id))
                        if reserva and reserva.estado_temporal == EstadoTmp.RESERVADO:
                            logger.debug("[trace_id=%s]|Estado temporal %s impide candidatura|Conductor id =%s",
                                trace_id,reserva.estado_temporal,conductor_id,)
                            continue
                    except NotFoundError:
                        logger.debug("[trace_id=%s]|Sin reserva temporal activa para conductor,esta libre|conductor_id=%s",
                            trace_id,conductor_id,)
                    except (RedisConnectionError, RedisTimeoutError) as e:
                        logger.exception("[trace_id=%s]|No se pudo acceder a registro de reservas|Tipo= %s|Detalle= %s",
                            trace_id,type(e).__name__,e,)
                        continue
                    except Exception as e:
                        logger.exception("[trace_id=%s]|No se pudo acceder a registro de reservas|Tipo= %s|Detalle= %s",
                            trace_id,type(e).__name__,e,)
                        continue
        
                    # Pasos 1, 2, 3 y 4 contra M3
                    if not _verificar_candidato_m3(
                        client=m3_client,conductor_id=conductor_id,tipo_vehiculo_requerido=query.tipo_vehiculo,
                        trace_id=trace_id,):
                        logger.info("[trace_id=%s]|Candidato descartado tras validación síncrona con M3|conductor_id=%s",
                            trace_id,conductor_id,)
                        continue
        
                    eta_estimado = max(1, round(distancia_km * 3))
                    candidato = Candidatos(
                        conductor_id=conductor_id,
                        distancia_origen_km=round(distancia_km, 2),
                        eta_retiro_minutos=eta_estimado,
                        tipo_vehiculo=query.tipo_vehiculo,
                    )
                    candidatos_radio.append(candidato)
        
                if candidatos_radio:
                    candidatos_finales = candidatos_radio
                    radio_aplicado = radio_km
                    break
        
        candidatos_finales.sort(key=lambda x: x.distancia_origen_km)
        
        if query.limite:
            candidatos_finales = candidatos_finales[: query.limite]
        
        if candidatos_finales:
            logger.info("[trace_id=%s]|Se encontraron candidatos.|Cantidad = %d|radio_aplicado_km=%.2f",
                trace_id,len(candidatos_finales),radio_aplicado,)
        else:
            logger.info("[trace_id=%s]|No se encontraron candidatos.|Se devuelve conductores vacio",trace_id,)
        
        return ResultadoBusquedaConductores(
            conductores=candidatos_finales,
            radio_aplicado_km=radio_aplicado,
            generado_en=datetime.now(timezone.utc),)
