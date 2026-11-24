import hashlib, logging
from typing import Any
from fastapi import Request
from app.db.cache_config import cache
from app.errores.exceptionsSemanticos import DependenciaNoDisponible,FaltaHeaderIdempotencia,HashBodyDiferente,RespuestaIdempotenteLista
from app.modelos.cache_models import RegistroIdempotencia

logger = logging.getLogger(__name__)

TTL_IDEMPOTENCIA_SEGUNDOS = 10800  # 3 horas según contrato

def calcular_hash_body(body_bytes: bytes) -> str:
    return hashlib.sha256(body_bytes).hexdigest()

def guardar_respuesta_idempotente(idempotency_key: str,body_hashin:str,status_code: int,body_dict: dict[str, Any],trace_id: str | None = None,) -> None:
    """Guarda en Redis el resultado de la operación con TTL de 3 horas y el mismo hash SHA-256."""
    clave = f"idempotency:{idempotency_key}"
    registro = RegistroIdempotencia(
        status_code=status_code,
        body=body_dict,
        body_hash=body_hashin,)
    try:
        cache.set(clave, registro.model_dump_json(), ex=TTL_IDEMPOTENCIA_SEGUNDOS)
        logger.info("[trace_id=%s]|Idempotencia guardada en Redis|key=%s|status=%s|ttl=%ss",
            trace_id,idempotency_key,status_code,TTL_IDEMPOTENCIA_SEGUNDOS,)
    except Exception as exc:
        logger.exception("[trace_id=%s]|Error al guardar idempotencia en Redis|key=%s|Tipo=%s|Detalle=%s",
            trace_id,idempotency_key,type(exc).__name__,exc,)
        raise DependenciaNoDisponible(detail="No se pudo guardar el registro de idempotencia en caché.",) from exc


async def verificar_idempotencia(request: Request) -> tuple[str, str]:
    trace_id = getattr(request.state, "request_id")
    idempotency_key = request.headers.get("Idempotency-Key") or request.headers.get("idempotencyKey")
    if not idempotency_key:
        logger.warning("[trace_id=%s]|Falta header Idempotency-Key", trace_id)
        raise FaltaHeaderIdempotencia()

    body_bytes = await request.body()
    body_hash = calcular_hash_body(body_bytes)
    clave = f"idempotency:{idempotency_key}"

    try:
        coincidencia_json = cache.get(clave)
        campo = (RegistroIdempotencia.model_validate_json(coincidencia_json)
            if coincidencia_json else None)
    except Exception as exc:
        logger.exception("[trace_id=%s]|Error al consultar/validar idempotencia en Redis|key=%s|Tipo=%s|Detalle=%s",
            trace_id,idempotency_key,type(exc).__name__,exc,)
        raise DependenciaNoDisponible(detail="No se pudo consultar el estado de idempotencia en caché.") from exc

    if campo is not None:
        if campo.body_hash != body_hash:
            logger.warning("[trace_id=%s]|Conflicto de hash para Idempotency-Key=%s",trace_id,idempotency_key,)
            raise HashBodyDiferente()
        #encontro idempotencia
        logger.info("[trace_id=%s]|Cache hit de idempotencia|key=%s|status=%s",trace_id,idempotency_key,campo.status_code,)
        raise RespuestaIdempotenteLista(status_code=campo.status_code, payload=campo.body)
    return idempotency_key,body_hash
