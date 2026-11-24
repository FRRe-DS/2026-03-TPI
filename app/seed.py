from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5
from app.db.cache_config import cache
from app.esquemas.esquemas import Coordenada
from app.modelos.cache_models import CacheEstOp, UbicacionesCond

def main() -> None:
    cache.ping()
    ahora = datetime.now(timezone.utc)

    for numero in range(1, 51):
        # IDs estables: volver a ejecutar la seed actualiza estos mismos conductores.
        conductor_id = uuid5(NAMESPACE_URL, f"tpi-m4-seed-conductor-{numero}")

        # 30 disponibles, 10 conectados pero no disponibles y 10 desconectados.
        connected = numero <= 40
        available = numero <= 30

        # Ubicaciones de prueba distribuidas cerca de Resistencia, Chaco.
        latitud = -27.451 + ((numero - 1) // 10) * 0.001
        longitud = -58.986 + ((numero - 1) % 10) * 0.001

        ubicacion = UbicacionesCond(
            pk=str(conductor_id),
            conductor_id=conductor_id,
            geo=Coordenada(latitud=latitud, longitud=longitud),
            timestamp_ubicacion=ahora,
        )
        ubicacion.save()
        ubicacion.expire(30)

        estado = CacheEstOp(
            pk=str(conductor_id),
            conductor_id=conductor_id,
            connected=connected,
            available=available,
            timestamp_evento=ahora,
        )
        estado.save()

    print("Seed completada: 50 conductores cargados en Redis.")

if __name__ == "__main__":
    main()