import hashlib,logging
from fastapi import Request
from fastapi.responses import JSONResponse
from app.db.cache_config import cache
from app.errores.exceptionsSemanticos import DependenciaNoDisponible,FaltaHeaderIdempotencia,HashBodyDiferente
from app.modelos.cache_models import RegistroIdempotencia

logger = logging.getLogger(__name__)

async def verificar_idempotencia(request: Request):
    trace_id = getattr(request.state, "request_id", None)
    # Extraer el header obligatorio exigido por el contrato
    idempotency_key = request.headers.get("idempotencyKey")
    if not idempotency_key:
        logger.warning("[trace_id=%s]|Falta header idempotencyKey en la solicitud",trace_id,)
        raise FaltaHeaderIdempotencia()

    # Calcular el hash SHA-256 del body actual para detectar reutilización con payload distinto
    body_bytes = await request.body()
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    clave = f"idempotency:{idempotency_key}"

    # Consultar y validar el registro en caché dentro de try para mapear fallos de Redis/datos a 503
    try:
        coincidencia_json = cache.get(clave)
        campo = (RegistroIdempotencia.model_validate_json(coincidencia_json) if coincidencia_json else None)
    except Exception as exc:
        logger.exception(
            "[trace_id=%s]|Error al consultar/validar idempotencia en Redis|key=%s|Tipo=%s|Detalle=%s",
            trace_id,idempotency_key,type(exc).__name__,exc,)
        raise DependenciaNoDisponible(detail="No se pudo consultar el estado de idempotencia en caché.") from exc

    if campo is not None:
        if campo.body_hash != body_hash:
            logger.warning("[trace_id=%s]|Conflicto de hash en idempotencyKey=%s",trace_id,idempotency_key,)
            raise HashBodyDiferente()
        logger.info("[trace_id=%s]|Respuesta idempotente recuperada desde caché|key=%s|status=%s",
            trace_id,idempotency_key,campo.status_code,)
        return JSONResponse(status_code=campo.status_code, content=campo.body)
    # Si no existe registro previo, se devuelve la clave para continuar con la ejecución normal
    return idempotency_key