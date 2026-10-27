from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from fastapi import FastAPI
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.middleware import RequestIdMiddleware
from app.core.observability import configure_logging
from app.core.problem_details import register_problem_details_handlers
from app.enrutador.estado_operativo import router as estado_operativo_router
from app.enrutador.eventos import prueba
from app.enrutador.reservas import router as reservas_router
from app.enrutador.rutas import router as rutas_router
from app.enrutador.ubicaciones import router as ubicaciones_router
from app.repositories.locations import RedisLocationRepository


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        redis_client: Redis | None = None
        try:
            if app_settings.redis_url:
                redis_client = Redis.from_url(
                    app_settings.redis_url,
                    decode_responses=True,
                    health_check_interval=30,
                )
                await redis_client.ping()
                application.state.location_repository = RedisLocationRepository(
                    redis_client,
                    ttl_seconds=app_settings.location_ttl_seconds,
                )
            else:
                application.state.location_repository = None
            yield
        finally:
            if redis_client is not None:
                await redis_client.aclose()

    application = FastAPI(
        title=app_settings.app_name,
        description="API de ubicación y disponibilidad de conductores.",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.state.clock = lambda: datetime.now(timezone.utc)
    application.add_middleware(RequestIdMiddleware)
    register_problem_details_handlers(application)
    application.include_router(prueba, prefix="/PruebaM4")
    application.include_router(ubicaciones_router)
    application.include_router(estado_operativo_router)
    application.include_router(reservas_router)
    application.include_router(rutas_router)

    @application.get("/")
    def read_home() -> dict[str, str]:
        return {
            "estado": "activo",
            "mensaje": "M4 corriendo correctamente en Docker",
        }

    return application


app = create_app()
