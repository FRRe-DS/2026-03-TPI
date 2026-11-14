import hashlib
from fastapi import Request, Response, HTTPException
from app.db.cache_config import cache
from app.modelos.cache_models import RegistroIdempotencia
from app.errores.exceptionsSemanticos import HashBodyDiferente, FaltaHeaderIdempotencia

async def verificar_idempotencia(request: Request, response: Response):
    # Extraer el header obligatorio exigido por el YAML
    idempotency_key = request.headers.get("idempotencyKey")
    if not idempotency_key:
        raise FaltaHeaderIdempotencia()

    # Calcular el hash SHA-256 del Body actual
    body_bytes = await request.body()
    body_hash = hashlib.sha256(body_bytes).hexdigest()

    # Armar la clave exacta para buscar en Redis
    coincidencia = f"idempotency:{idempotency_key}"

    # Consultar en Redis si ya existe el casillero
    coincidencia_json = cache.get(coincidencia)
    if coincidencia_json:
        # Deserializar usando el BaseModel de Pydantic
        campo = RegistroIdempotencia.model_validate_json(coincidencia_json)
        # Validar integridad: misma llave pero datos distintos -> Error 409 Conflict
        if campo.body_hash != body_hash:
            raise HashBodyDiferente()
        # Cortamos la ejecución devolviendo la respuesta ya guardada mediante HTTPException
        raise HTTPException(
            status_code=campo.status_code,
            detail=campo.body
        )

    # Si la llave NO existe, devolvemos la clave para que siga hacia el endpoint
    return idempotency_key
