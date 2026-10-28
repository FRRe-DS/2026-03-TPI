import asyncio
from typing import Protocol

from fastapi import APIRouter, Request
from redis.exceptions import RedisError
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import DependencyUnavailableError
from app.database import engine as configured_database_engine
from app.schemas.schemas import LivenessResponse, ReadinessResponse

router = APIRouter(tags=["Salud"])


class RedisPingClient(Protocol):
    async def ping(self) -> bool: ...


def _database_is_ready(database_engine: Engine | None) -> bool:
    if database_engine is None:
        return False
    try:
        with database_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError, TimeoutError):
        return False
    return True


@router.get("/health/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse(status="UP")


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(request: Request) -> ReadinessResponse:
    database_ready, redis_ready = await asyncio.gather(
        asyncio.to_thread(
            _database_is_ready,
            getattr(
                request.app.state,
                "database_engine",
                configured_database_engine,
            ),
        ),
        _redis_is_ready(getattr(request.app.state, "redis_client", None)),
    )
    if not database_ready or not redis_ready:
        raise DependencyUnavailableError(
            "Una o más dependencias críticas no están disponibles."
        )
    return ReadinessResponse(status="READY")


async def _redis_is_ready(redis_client: RedisPingClient | None) -> bool:
    if redis_client is None:
        return False
    try:
        return bool(await redis_client.ping())
    except (RedisError, OSError, TimeoutError):
        return False
