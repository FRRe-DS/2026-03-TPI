from collections.abc import Awaitable, Callable

from fastapi import Request

from app.core.errors import DependencyUnavailableError
from app.schemas.schemas import EstimacionRuta, PuntoGeografico, TipoVehiculo

RouteEstimator = Callable[
    [PuntoGeografico, PuntoGeografico, TipoVehiculo | None],
    Awaitable[EstimacionRuta],
]


def get_route_estimator(request: Request) -> RouteEstimator:
    estimator = getattr(request.app.state, "route_estimator", None)
    if estimator is None:
        raise DependencyUnavailableError(
            "El proveedor de estimación de rutas no está configurado."
        )
    return estimator
