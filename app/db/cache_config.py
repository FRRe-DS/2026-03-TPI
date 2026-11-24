import os
from redis_om import get_redis_connection

# 1. Intentamos leer si hay un Host externo/productivo definido
# 2. Si no existe, usamos el REDIS_HOST que maneja el DNS de Docker ("m4cache")
#si el framework de testing es externo al contenedor, debe hacer consultas al localhost y puerto del os
#contrario el framework "vive" en el contenedor y necesita la misma referencia interna
fwexterno = os.getenv("FRAMEWORK_TESTING_EXTERNO", "false").lower() == "true"

if fwexterno:
    REDIS_HOST = os.getenv("REDIS_EXTERNAL_HOST", "localhost")
else:
    REDIS_HOST = os.getenv("REDIS_HOST", "m4cache")

#REDIS_HOST = os.getenv("REDIS_HOST") or os.getenv("REDIS_EXTERNAL_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

if not REDIS_HOST:
    raise RuntimeError("CRÍTICO: No se pudo determinar la dirección de Redis.")

cache = get_redis_connection(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)