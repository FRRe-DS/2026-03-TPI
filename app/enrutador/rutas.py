import asyncio
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Query

from app.core.auth import AuthenticatedPrincipal, get_authenticated_principal
from app.core.errors import DependencyTimeoutError, DependencyUnavailableError
from app.schemas.schemas import (
    EstimacionRuta,
    PuntoGeografico,
    TipoVehiculo,
)
from app.servicios.route_estimation import RouteEstimator, get_route_estimator

router = APIRouter(prefix="/api/v1/rutas", tags=["Rutas"])


@router.get("/estimacion", response_model=EstimacionRuta)
async def estimar_ruta(
    origen_latitud: Annotated[float, Query(ge=-90, le=90)],
    origen_longitud: Annotated[float, Query(ge=-180, le=180)],
    destino_latitud: Annotated[float, Query(ge=-90, le=90)],
    destino_longitud: Annotated[float, Query(ge=-180, le=180)],
    tipo_vehiculo: TipoVehiculo | None = None,
    _principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    estimator: RouteEstimator = Depends(get_route_estimator),
) -> EstimacionRuta:
    try:
        return await estimator(
            PuntoGeografico(latitud=origen_latitud, longitud=origen_longitud),
            PuntoGeografico(latitud=destino_latitud, longitud=destino_longitud),
            tipo_vehiculo,
        )
    except (asyncio.TimeoutError, httpx.TimeoutException) as error:
        raise DependencyTimeoutError(
            "El proveedor de rutas excedió el tiempo de espera."
        ) from error
    except httpx.RequestError as error:
        raise DependencyUnavailableError(
            "El proveedor de rutas no está disponible."
        ) from error
