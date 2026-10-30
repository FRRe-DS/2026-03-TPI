import hashlib
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from ..db.cache_config import cache
from ..modelos.cache_models import RegistroIdempotencia
from .exceptionsSemanticos import HashBodyDiferente, FaltaHeaderIdempotencia
#se supone que para cada "consulta" la idempotency_key es unica, como solo existe una por body, que cambie el 
#body no tiene sentido

async def verificar_idempotencia(request: Request, response: Response):
    #Extraer el header obligatorio exigido por el YAML
    idempotency_key = request.headers.get("idempotencyKey")
    
    if not idempotency_key:
        raise FaltaHeaderIdempotencia()

    #Calcular el hash SHA-256 del Body actual (policía anti-fraude)
    body_bytes = await request.body()
    body_hash = hashlib.sha256(body_bytes).hexdigest()

    #Armar la clave (key) exacta para buscar en Redis
    coincidencia = f"idempotency:{idempotency_key}"

    # Consultar en Redis si ya existe el casillero
    coincidencia_json = cache.get(coincidencia)

    if coincidencia_json:
        # Deserializar usando nuestro BaseModel de Pydantic
        campo = RegistroIdempotencia.model_validate_json(coincidencia_json)
        
        # Validar integridad: misma llave pero datos distintos -> Error 409 Conflict
        if coincidencia.body_hash != body_hash:
            raise HashBodyDiferente()
        
        # Si todo coincide perfectamente, devolvemos la respuesta cacheada (Cumple con el 200 OK del YAML)
        return JSONResponse(
            status_code=campo.status_code,
            content=campo.body
        )
    #Si la llave NO existe, cedemos el control para que se ejecute el endpoint de negocio
    yield idempotency_key
