from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.middleware import RequestIdMiddleware
from app.core.observability import configure_logging
from app.core.problem_details import register_problem_details_handlers
from app.enrutador.eventos import prueba


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    app_settings = settings or get_settings()
    application = FastAPI(
        title=app_settings.app_name,
        description="API de ubicación y disponibilidad de conductores.",
        version="1.0.0",
    )
    application.add_middleware(RequestIdMiddleware)
    register_problem_details_handlers(application)
    application.include_router(prueba, prefix="/PruebaM4")

    @application.get("/")
    def read_home() -> dict[str, str]:
        return {
            "estado": "activo",
            "mensaje": "M4 corriendo correctamente en Docker",
        }

    return application


app = create_app()
