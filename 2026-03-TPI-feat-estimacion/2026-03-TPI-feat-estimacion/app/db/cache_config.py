import os
from redis_om import get_redis_connection

# 1. Intentamos leer si hay un Host externo/productivo definido
# 2. Si no existe, usamos el REDIS_HOST que maneja el DNS de Docker ("m4cache")
REDIS_HOST = os.getenv("REDIS_EXTERNAL_HOST") or os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

if not REDIS_HOST:
    raise RuntimeError("CRÍTICO: No se pudo determinar la dirección de Redis.")

cache = get_redis_connection(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)