from collections.abc import Awaitable, Callable

import asyncio
import httpx
from fastapi import Request

from app.core.errors import DependencyTimeoutError, DependencyUnavailableError
from app.schemas.schemas import EstimacionRuta, PuntoGeografico, TipoVehiculo

RouteEstimator = Callable[
    [PuntoGeografico, PuntoGeografico, TipoVehiculo | None],
    Awaitable[EstimacionRuta],
]


def get_route_estimator(request: Request) -> RouteEstimator:
    estimator = get_optional_route_estimator(request)
    if estimator is None:
        raise DependencyUnavailableError(
            "El proveedor de estimación de rutas no está configurado."
        )
    return estimator


def get_optional_route_estimator(request: Request) -> RouteEstimator | None:
    estimator = getattr(request.app.state, "route_estimator", None)
    return estimator


async def estimate_route(
    estimator: RouteEstimator,
    origin: PuntoGeografico,
    destination: PuntoGeografico,
    vehicle: TipoVehiculo | None,
) -> EstimacionRuta:
    try:
        return await estimator(origin, destination, vehicle)
    except (asyncio.TimeoutError, httpx.TimeoutException) as error:
        raise DependencyTimeoutError(
            "El proveedor de rutas excedió el tiempo de espera."
        ) from error
    except httpx.RequestError as error:
        raise DependencyUnavailableError(
            "El proveedor de rutas no está disponible."
        ) from error
