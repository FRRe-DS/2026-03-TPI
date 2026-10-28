import asyncio
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from redis.asyncio import Redis

from app.core.config import Settings
from app.main import create_app
from app.repositories.dependencies import get_location_repository
from app.repositories.locations import LocationWriteResult, RedisLocationRepository
from app.schemas.schemas import ActualizarUbicacion


def test_redis_location_upsert_is_conditional_and_atomic() -> None:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        pytest.skip("REDIS_URL no está configurado.")

    async def scenario() -> None:
        client = Redis.from_url(redis_url, decode_responses=True)
        conductor_id = uuid4()
        repository = RedisLocationRepository(client)
        key = repository.key_for(conductor_id)
        timestamp = datetime.now(timezone.utc)
        try:
            await client.ping()
            first = ActualizarUbicacion(
                conductor_id=conductor_id,
                latitud=-27.4512,
                longitud=-58.9866,
                timestamp_ubicacion=timestamp,
            )
            assert await repository.upsert(first) is LocationWriteResult.CREATED

            stored = await repository.get_current(conductor_id)
            assert stored is not None
            assert stored.latitud == first.latitud
            assert stored.longitud == first.longitud
            assert stored.expira_en - stored.recibida_en == timedelta(seconds=30)
            assert await client.ttl(key) <= 30

            assert (
                await repository.upsert(first)
                is LocationWriteResult.IDEMPOTENT
            )
            assert (
                await repository.upsert(
                    first.model_copy(update={"latitud": -27.45})
                )
                is LocationWriteResult.CONFLICT
            )
            assert (
                await repository.upsert(
                    first.model_copy(
                        update={"timestamp_ubicacion": timestamp - timedelta(seconds=1)}
                    )
                )
                is LocationWriteResult.STALE
            )

            newer = first.model_copy(
                update={
                    "timestamp_ubicacion": timestamp + timedelta(seconds=1),
                    "latitud": -27.46,
                }
            )
            assert (
                await repository.upsert(newer) is LocationWriteResult.APPLIED
            )
            updated = await repository.get_current(conductor_id)
            assert updated is not None
            assert updated.latitud == newer.latitud
        finally:
            await client.delete(key)
            await client.aclose()

    asyncio.run(scenario())


def test_redis_location_expires_at_configured_ttl() -> None:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        pytest.skip("REDIS_URL no está configurado.")

    async def scenario() -> None:
        client = Redis.from_url(redis_url, decode_responses=True)
        conductor_id = uuid4()
        repository = RedisLocationRepository(client, ttl_seconds=1)
        key = repository.key_for(conductor_id)
        try:
            await client.ping()
            location = ActualizarUbicacion(
                conductor_id=conductor_id,
                latitud=0,
                longitud=0,
                timestamp_ubicacion=datetime.now(timezone.utc),
            )
            assert await repository.upsert(location) is LocationWriteResult.CREATED
            assert await repository.get_current(conductor_id) is not None

            ttl = await client.ttl(key)
            assert 0 < ttl <= 1
            await client.pexpire(key, 0)

            assert await repository.get_current(conductor_id) is None
        finally:
            await client.delete(key)
            await client.aclose()

    asyncio.run(scenario())


def test_fastapi_lifespan_connects_and_closes_redis_repository() -> None:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        pytest.skip("REDIS_URL no está configurado.")

    application = create_app(Settings(_env_file=None, redis_url=redis_url))

    @application.get("/test/location-repository")
    def location_repository_is_injected(
        repository: RedisLocationRepository = Depends(get_location_repository),
    ) -> dict[str, bool]:
        return {"configured": isinstance(repository, RedisLocationRepository)}

    with TestClient(application) as client:
        assert client.get("/").status_code == 200
        assert client.get("/test/location-repository").json() == {
            "configured": True
        }
        assert isinstance(
            application.state.location_repository, RedisLocationRepository
        )
