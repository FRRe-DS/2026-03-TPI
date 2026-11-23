import logging, math, os,time
from typing import Callable
from fastapi import Depends, Request
from redis.exceptions import RedisError
from app.db.cache_config import cache
from app.errores.exceptionsSemanticos import LimiteExcedido
from app.seguridad.authManager import validar_token_keycloak

logger = logging.getLogger(__name__)

# (max_solicitudes, ventana_segundos) por operación
LIMITES_POR_OPERACION: dict[str, tuple[int, int]] = {
    "actualizar_ubicacion": (
        int(os.getenv("RL_UBICACION_MAX", "600")),int(os.getenv("RL_UBICACION_VENTANA", "60")),
    ),
    "actualizar_estado_operativo": (
        int(os.getenv("RL_ESTADO_MAX", "300")),int(os.getenv("RL_ESTADO_VENTANA", "60")),
    ),
    "buscar_conductores_cercanos": (
        int(os.getenv("RL_CERCANOS_MAX", "240")),int(os.getenv("RL_CERCANOS_VENTANA", "60")),
    ),
    "reservar_conductor": (
        int(os.getenv("RL_RESERVA_MAX", "180")),int(os.getenv("RL_RESERVA_VENTANA", "60")),
    ),
    "estimar_ruta": (
        int(os.getenv("RL_ESTIMACION_MAX", "180")),int(os.getenv("RL_ESTIMACION_VENTANA", "60")),
    ),
    "geocodificar": (
        int(os.getenv("RL_GEOCODIF_MAX", "120")),int(os.getenv("RL_GEOCODIF_VENTANA", "60")),
    ),
}

LIMITE_DEFAULT: tuple[int, int] = (
    int(os.getenv("RL_DEFAULT_MAX", "120")),int(os.getenv("RL_DEFAULT_VENTANA", "60")),)

def _obtener_consumidor(request: Request, claims: dict | None) -> str:
    if claims:
        consumidor = claims.get("azp") or claims.get("client_id") or claims.get("sub")
        if consumidor:
            return f"jwt:{consumidor}"
    ip = request.client.host if request.client else "desconocido"
    logger.debug("Rate limit usando fallback de IP")
    return f"ip:{ip}"

def _calcular_retry_after(clave: str, ventana_segundos: int) -> int:
    try:
        ttl = cache.ttl(clave)
        if isinstance(ttl, int) and ttl > 0:
            logger.debug("Retry-After obtenido desde TTL de caché|Clave=%s|TTL=%ds", clave, ttl)
            return max(1, ttl)
        logger.debug("TTL no positivo o no entero (%s) para %s; usando cálculo de ventana", ttl, clave)
    except RedisError as exc:
        logger.debug("Error al consultar TTL para Retry-After; usando fallback de ventana|Clave=%s|Tipo=%s|Detalle=%s",
            clave,type(exc).__name__,exc,)
        
    ahora = time.time()
    fin_ventana = (math.floor(ahora / ventana_segundos) + 1) * ventana_segundos
    retry_after = max(1, math.ceil(fin_ventana - ahora))
    logger.debug("Retry-After calculado por ventana|Clave=%s|RetryAfter=%ds", clave, retry_after)
    return retry_after

def verificar_rate_limit(operacion: str) -> Callable:
    max_solicitudes, ventana_segundos = LIMITES_POR_OPERACION.get(operacion, LIMITE_DEFAULT)

    async def dependencia_rate_limit(request: Request,claims: dict = Depends(validar_token_keycloak),) -> None:
        consumidor = _obtener_consumidor(request, claims)
        clave = f"rl:{operacion}:{consumidor}"

        try:
            conteo = cache.incr(clave)
            if conteo == 1:
                cache.expire(clave, ventana_segundos)
                logger.debug("Ventana de rate limit iniciada|Clave=%s|Ventana=%ds|Max=%d",clave,ventana_segundos,max_solicitudes,)
            else:
                logger.debug("Rate limit incrementado|Clave=%s|Conteo=%d/%d",clave,conteo,max_solicitudes,)

            if conteo > max_solicitudes:
                retry_after = _calcular_retry_after(clave, ventana_segundos)
                logger.warning("Rate limit excedido (429)|Operacion=%s|Consumidor=%s|Conteo=%d/%d|Retry-After=%ds",
                    operacion,consumidor,conteo,max_solicitudes,retry_after,)
                raise LimiteExcedido(retry_after=retry_after,)

        except LimiteExcedido:
            raise
        except RedisError as exc:
            logger.warning(
                "Error de Redis en rate limit; aplicando fail-open|Operacion=%s|Consumidor=%s|Tipo=%s|Detalle=%s",
                operacion,consumidor,type(exc).__name__,exc,)

    return dependencia_rate_limit
