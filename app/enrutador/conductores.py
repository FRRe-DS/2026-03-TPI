import math
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.clients.m3 import ClienteM3
from app.core.auth import AuthenticatedPrincipal, get_authenticated_principal
from app.core.errors import DomainError
from app.repositories.dependencies import (
    get_location_repository,
    get_operational_repository,
)
from app.repositories.locations import LocationRepository
from app.repositories.m3_dependencies import get_m3_client
from app.repositories.operational import SqlAlchemyOperationalRepository
from app.schemas.schemas import (
    PuntoGeografico,
    ResultadoBusquedaConductores,
    TipoVehiculo,
)
from app.servicios.coverage import CoverageArea
from app.servicios.proximity import find_nearby_candidates
from app.servicios.route_estimation import (
    RouteEstimator,
    get_optional_route_estimator,
)

router = APIRouter(prefix="/api/v1/conductores", tags=["Proximidad"])


@router.get(
    "/cercanos",
    response_model=ResultadoBusquedaConductores,
    responses={
        200: {
            "headers": {
                "Cache-Control": {
                    "description": "La respuesta con ubicación no debe almacenarse.",
                    "schema": {"type": "string", "const": "no-store"},
                }
            }
        }
    },
)
async def buscar_conductores_cercanos(
    request: Request,
    origen_latitud: Annotated[float, Query(ge=-90, le=90)],
    origen_longitud: Annotated[float, Query(ge=-180, le=180)],
    tipo_vehiculo: TipoVehiculo,
    radio_km: Annotated[
        float,
        Query(
            gt=0,
            description="Radio de búsqueda en km; predeterminado 5 km.",
        ),
    ] = 5.0,
    radio_maximo_km: Annotated[
        float | None,
        Query(
            gt=0,
            description=(
                "Techo para repetir búsquedas; no amplía automáticamente "
                "el radio solicitado."
            ),
            json_schema_extra={"example": 20.0},
        ),
    ] = None,
    limite: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Cantidad máxima de candidatos; predeterminado 20.",
        ),
    ] = 20,
    _principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    location_repository: LocationRepository = Depends(get_location_repository),
    operational_repository: SqlAlchemyOperationalRepository = Depends(
        get_operational_repository
    ),
    m3_client: ClienteM3 = Depends(get_m3_client),
    route_estimator: RouteEstimator | None = Depends(get_optional_route_estimator),
) -> ResultadoBusquedaConductores:
    settings = request.app.state.settings
    applied_radius = (
        settings.default_search_radius_km
        if "radio_km" not in request.query_params
        else radio_km
    )
    if radio_maximo_km is not None and (
        not math.isfinite(radio_maximo_km)
        or radio_maximo_km < applied_radius
        or radio_maximo_km > settings.max_search_radius_km
    ):
        raise DomainError(
            status_code=422,
            code="INVALID_MAX_SEARCH_RADIUS",
            title="Radio máximo de búsqueda inválido",
            detail=(
                "El radio máximo debe ser igual o mayor al radio de búsqueda "
                "y no superar el máximo configurado."
            ),
        )

    coverage: CoverageArea | None = request.app.state.coverage
    return await find_nearby_candidates(
        origin=PuntoGeografico(
            latitud=origen_latitud,
            longitud=origen_longitud,
        ),
        requested_vehicle=tipo_vehiculo,
        radius_km=applied_radius,
        limit=(
            min(20, settings.max_candidates)
            if "limite" not in request.query_params
            else limite
        ),
        max_radius_km=settings.max_search_radius_km,
        max_limit=settings.max_candidates,
        location_repository=location_repository,
        operational_repository=operational_repository,
        m3_client=m3_client,
        coverage=coverage,
        route_estimator=route_estimator,
        allow_eta_degradation=settings.proximity_eta_degradation_enabled,
        route_timeout_seconds=settings.maps_timeout_seconds,
        now=request.app.state.clock(),
    )
