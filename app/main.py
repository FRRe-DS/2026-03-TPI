from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from app.clients.m3 import ClienteM3
from app.clients.geocoding import NominatimGeocodingAdapter
from fastapi import FastAPI
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.database import engine as database_engine
from app.servicios.coverage import CoverageArea
from app.core.middleware import RequestIdMiddleware
from app.core.observability import configure_logging
from app.core.problem_details import register_problem_details_handlers
from app.enrutador.estado_operativo import router as estado_operativo_router
from app.enrutador.conductores import router as conductores_router
from app.enrutador.geocodificaciones import router as geocodificaciones_router
from app.enrutador.health import router as health_router
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
        m3_client: ClienteM3 | None = None
        try:
            if app_settings.redis_url:
                redis_client = Redis.from_url(
                    app_settings.redis_url,
                    decode_responses=True,
                    health_check_interval=30,
                )
                application.state.location_repository = RedisLocationRepository(
                    redis_client,
                    ttl_seconds=app_settings.location_ttl_seconds,
                )
            else:
                application.state.location_repository = None
            application.state.redis_client = redis_client
            if (
                app_settings.m3_base_url is not None
                and app_settings.m3_service_token is not None
                and app_settings.m3_eligibility_path is not None
            ):
                m3_client = ClienteM3(
                    base_url=app_settings.m3_base_url,
                    service_token=app_settings.m3_service_token,
                    eligibility_path=app_settings.m3_eligibility_path,
                    timeout_seconds=app_settings.m3_timeout_seconds,
                )
            application.state.m3_client = m3_client
            application.state.geocoding_adapter = NominatimGeocodingAdapter(
                timeout_seconds=app_settings.geocoding_timeout_seconds,
                user_agent=app_settings.geocoding_user_agent,
                min_delay_seconds=app_settings.geocoding_min_delay_seconds,
            )
            application.state.coverage = (
                CoverageArea.from_geojson(app_settings.coverage_geojson)
                if app_settings.coverage_geojson
                else None
            )
            yield
        finally:
            if m3_client is not None:
                await m3_client.aclose()
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
    application.state.database_engine = database_engine
    application.state.redis_client = None
    application.state.m3_client = None
    application.state.geocoding_adapter = None
    application.state.route_estimator = None
    application.state.coverage = None
    application.add_middleware(RequestIdMiddleware)
    register_problem_details_handlers(application)
    application.include_router(prueba, prefix="/PruebaM4")
    application.include_router(conductores_router)
    application.include_router(geocodificaciones_router)
    application.include_router(ubicaciones_router)
    application.include_router(estado_operativo_router)
    application.include_router(reservas_router)
    application.include_router(rutas_router)
    application.include_router(health_router)

    @application.get("/")
    def read_home() -> dict[str, str]:
        return {
            "estado": "activo",
            "mensaje": "M4 corriendo correctamente en Docker",
        }

    return application


app = create_app()
