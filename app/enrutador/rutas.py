from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import AuthenticatedPrincipal, get_authenticated_principal
from app.schemas.schemas import (
    EstimacionRuta,
    PuntoGeografico,
    TipoVehiculo,
)
from app.servicios.coverage import require_coverage
from app.servicios.route_estimation import (
    RouteEstimator,
    estimate_route,
    get_route_estimator,
)

router = APIRouter(prefix="/api/v1/rutas", tags=["Rutas"])


@router.get("/estimacion", response_model=EstimacionRuta)
async def estimar_ruta(
    request: Request,
    origen_latitud: Annotated[float, Query(ge=-90, le=90)],
    origen_longitud: Annotated[float, Query(ge=-180, le=180)],
    destino_latitud: Annotated[float, Query(ge=-90, le=90)],
    destino_longitud: Annotated[float, Query(ge=-180, le=180)],
    tipo_vehiculo: TipoVehiculo | None = None,
    _principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    estimator: RouteEstimator = Depends(get_route_estimator),
) -> EstimacionRuta:
    origin = PuntoGeografico(latitud=origen_latitud, longitud=origen_longitud)
    destination = PuntoGeografico(
        latitud=destino_latitud,
        longitud=destino_longitud,
    )
    require_coverage(request.app.state.coverage, origin)
    require_coverage(request.app.state.coverage, destination)
    return await estimate_route(
        estimator,
        origin,
        destination,
        tipo_vehiculo,
        timeout_seconds=request.app.state.settings.maps_timeout_seconds,
    )
