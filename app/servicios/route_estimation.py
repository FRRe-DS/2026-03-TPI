import asyncio
import math
from collections.abc import Awaitable, Callable, Mapping

import httpx
from fastapi import Request
from pydantic import ValidationError

from app.core.errors import DependencyTimeoutError, DependencyUnavailableError
from app.schemas.schemas import (
    EstimacionRuta,
    FuenteEstimacion,
    PuntoGeografico,
    TipoVehiculo,
)

RouteEstimator = Callable[
    [PuntoGeografico, PuntoGeografico, TipoVehiculo | None],
    Awaitable[EstimacionRuta | Mapping[str, object]],
]


class RouteEstimatorAdapter:
    def __init__(self, provider: RouteEstimator) -> None:
        self._provider = provider

    async def __call__(
        self,
        origin: PuntoGeografico,
        destination: PuntoGeografico,
        vehicle: TipoVehiculo | None,
    ) -> EstimacionRuta:
        estimate = await self._provider(origin, destination, vehicle)
        try:
            result = EstimacionRuta.model_validate(estimate)
        except ValidationError as error:
            raise DependencyUnavailableError(
                "El proveedor de rutas devolvió una respuesta inválida."
            ) from error

        if (
            result.origen != origin
            or result.destino != destination
            or result.fuente is not FuenteEstimacion.PROVEEDOR_MAPA
        ):
            raise DependencyUnavailableError(
                "El proveedor de rutas devolvió una estimación inconsistente."
            )
        return result


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
    *,
    timeout_seconds: float,
) -> EstimacionRuta:
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds debe ser positivo y finito.")
    try:
        return await asyncio.wait_for(
            RouteEstimatorAdapter(estimator)(origin, destination, vehicle),
            timeout=timeout_seconds,
        )
    except (asyncio.TimeoutError, httpx.TimeoutException) as error:
        raise DependencyTimeoutError(
            "El proveedor de rutas excedió el tiempo de espera."
        ) from error
    except httpx.RequestError as error:
        raise DependencyUnavailableError(
            "El proveedor de rutas no está disponible."
        ) from error
