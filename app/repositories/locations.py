import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Protocol
from uuid import UUID

from redis.asyncio import Redis

from app.schemas.schemas import ActualizarUbicacion


class LocationWriteResult(str, Enum):
    APPLIED = "APPLIED"
    IDEMPOTENT = "IDEMPOTENT"
    STALE = "STALE"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True)
class StoredLocation:
    conductor_id: UUID
    latitud: float
    longitud: float
    timestamp_ubicacion: datetime
    recibida_en: datetime
    expira_en: datetime


class LocationRepository(Protocol):
    async def upsert(self, location: ActualizarUbicacion) -> LocationWriteResult: ...

    async def get_current(self, conductor_id: UUID) -> StoredLocation | None: ...


_UPSERT_IF_NEWER = """
local current = redis.call('GET', KEYS[1])
if current then
    local previous = cjson.decode(current)
    local old_timestamp = tonumber(previous.timestamp_epoch)
    local new_timestamp = tonumber(ARGV[1])
    if new_timestamp < old_timestamp then
        return -1
    end
    if new_timestamp == old_timestamp then
        if tonumber(previous.latitud) == tonumber(ARGV[3])
            and tonumber(previous.longitud) == tonumber(ARGV[4]) then
            return 0
        end
        return -2
    end
end
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[5])
return 1
"""

_WRITE_RESULTS = {
    1: LocationWriteResult.APPLIED,
    0: LocationWriteResult.IDEMPOTENT,
    -1: LocationWriteResult.STALE,
    -2: LocationWriteResult.CONFLICT,
}


class RedisLocationRepository:
    def __init__(
        self,
        client: Redis,
        *,
        ttl_seconds: int = 30,
    ) -> None:
        if ttl_seconds < 1:
            raise ValueError("El TTL de ubicación debe ser positivo.")
        self._client = client
        self._ttl_seconds = ttl_seconds

    @staticmethod
    def key_for(conductor_id: UUID) -> str:
        return f"m4:location:{conductor_id}"

    async def upsert(self, location: ActualizarUbicacion) -> LocationWriteResult:
        received_at = datetime.now(timezone.utc)
        expires_at = received_at + timedelta(seconds=self._ttl_seconds)
        document = {
            "conductor_id": str(location.conductor_id),
            "latitud": location.latitud,
            "longitud": location.longitud,
            "timestamp_ubicacion": location.timestamp_ubicacion.isoformat(),
            "timestamp_epoch": location.timestamp_ubicacion.timestamp(),
            "recibida_en": received_at.isoformat(),
            "expira_en": expires_at.isoformat(),
        }
        result = await self._client.eval(
            _UPSERT_IF_NEWER,
            1,
            self.key_for(location.conductor_id),
            location.timestamp_ubicacion.timestamp(),
            json.dumps(document, separators=(",", ":")),
            location.latitud,
            location.longitud,
            self._ttl_seconds,
        )
        try:
            return _WRITE_RESULTS[int(result)]
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("Redis devolvió un resultado de upsert desconocido.") from exc

    async def get_current(self, conductor_id: UUID) -> StoredLocation | None:
        raw_value = await self._client.get(self.key_for(conductor_id))
        if raw_value is None:
            return None

        payload = json.loads(raw_value)
        return StoredLocation(
            conductor_id=UUID(payload["conductor_id"]),
            latitud=float(payload["latitud"]),
            longitud=float(payload["longitud"]),
            timestamp_ubicacion=datetime.fromisoformat(
                payload["timestamp_ubicacion"]
            ).astimezone(timezone.utc),
            recibida_en=datetime.fromisoformat(payload["recibida_en"]).astimezone(
                timezone.utc
            ),
            expira_en=datetime.fromisoformat(payload["expira_en"]).astimezone(
                timezone.utc
            ),
        )
