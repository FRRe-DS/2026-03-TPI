import asyncio
import math
from datetime import datetime, timezone
from uuid import UUID

from app.clients.m3 import ClienteM3, ElegibilidadConductor
from app.core.errors import (
    DependencyTimeoutError,
    DependencyUnavailableError,
    DomainError,
)
from app.models import EstadoOperativoORM
from app.repositories.locations import LocationRepository, StoredLocation
from app.repositories.operational import SqlAlchemyOperationalRepository
from app.schemas.schemas import (
    Candidato,
    PuntoGeografico,
    ResultadoBusquedaConductores,
    TipoVehiculo,
)
from app.servicios.coverage import CoverageArea, require_coverage
from app.servicios.route_estimation import RouteEstimator, estimate_route

EARTH_RADIUS_KM = 6371.0088
M3_CONCURRENCY_LIMIT = 10


def linear_distance_km(origin: PuntoGeografico, location: StoredLocation) -> float:
    origin_latitude = math.radians(origin.latitud)
    location_latitude = math.radians(location.latitud)
    latitude_delta = location_latitude - origin_latitude
    longitude_delta = math.radians(location.longitud - origin.longitud)
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(origin_latitude)
        * math.cos(location_latitude)
        * math.sin(longitude_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, haversine)))


async def find_nearby_candidates(
    *,
    origin: PuntoGeografico,
    requested_vehicle: TipoVehiculo,
    radius_km: float,
    limit: int,
    max_radius_km: float,
    max_limit: int,
    location_repository: LocationRepository,
    operational_repository: SqlAlchemyOperationalRepository,
    m3_client: ClienteM3,
    coverage: CoverageArea | None,
    route_estimator: RouteEstimator | None = None,
    allow_eta_degradation: bool = True,
    route_timeout_seconds: float = 5.0,
    now: datetime | None = None,
) -> ResultadoBusquedaConductores:
    if (
        not math.isfinite(max_radius_km)
        or max_radius_km <= 0
        or not math.isfinite(radius_km)
        or radius_km <= 0
        or radius_km > max_radius_km
    ):
        raise DomainError(
            status_code=422,
            code="INVALID_SEARCH_RADIUS",
            title="Radio de búsqueda inválido",
            detail="El radio debe ser positivo y no superar el máximo configurado.",
        )
    if not 1 <= limit <= min(max_limit, 100):
        raise DomainError(
            status_code=422,
            code="INVALID_SEARCH_LIMIT",
            title="Límite de búsqueda inválido",
            detail="El límite debe estar entre uno y el máximo permitido.",
        )
    require_coverage(coverage, origin)
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("now debe incluir zona horaria.")
    current_time = current_time.astimezone(timezone.utc)
    local_states = operational_repository.list_available_states()
    geographically_eligible: list[tuple[EstadoOperativoORM, StoredLocation, float]] = []

    for state in local_states:
        location = await location_repository.get_current(state.conductor_id)
        if location is None or location.expira_en <= current_time:
            continue
        driver_point = PuntoGeografico(
            latitud=location.latitud,
            longitud=location.longitud,
        )
        if coverage is None or not coverage.covers(driver_point):
            continue
        distance = linear_distance_km(origin, location)
        if distance <= radius_km:
            geographically_eligible.append((state, location, distance))

    reservation_candidates: list[tuple[EstadoOperativoORM, StoredLocation, float]] = []
    for candidate in geographically_eligible:
        state, _, _ = candidate
        reservation = operational_repository.get_reservation(state.conductor_id)
        if (
            reservation is not None
            and reservation.estado_temporal == "RESERVADO"
            and reservation.expira_en is not None
            and reservation.expira_en > current_time
        ):
            continue
        reservation_candidates.append(candidate)

    semaphore = asyncio.Semaphore(M3_CONCURRENCY_LIMIT)

    async def verify(
        candidate: tuple[EstadoOperativoORM, StoredLocation, float],
    ) -> tuple[EstadoOperativoORM, StoredLocation, float, ElegibilidadConductor]:
        state, location, distance = candidate
        async with semaphore:
            eligibility = await m3_client.get_eligibility(state.conductor_id)
        return state, location, distance, eligibility

    verified = await asyncio.gather(
        *(verify(candidate) for candidate in reservation_candidates)
    )

    results: list[tuple[Candidato, float, StoredLocation]] = []
    for state, location, distance, eligibility in verified:
        if not eligibility.habilitado_para(requested_vehicle):
            continue
        results.append(
            (
                Candidato(
                    conductor_id=state.conductor_id,
                    distancia_origen_km=distance,
                    tipo_vehiculo=requested_vehicle,
                ),
                distance,
                location,
            )
        )
    results.sort(key=lambda result: (result[1], str(result[0].conductor_id)))

    selected = results[:limit]
    if route_estimator is None and selected and not allow_eta_degradation:
        raise DependencyUnavailableError(
            "El proveedor de estimación de rutas no está configurado."
        )

    eta_semaphore = asyncio.Semaphore(M3_CONCURRENCY_LIMIT)

    async def add_eta(
        result: tuple[Candidato, float, StoredLocation],
    ) -> Candidato:
        candidate, _, location = result
        if route_estimator is None:
            return candidate
        driver_location = PuntoGeografico(
            latitud=location.latitud,
            longitud=location.longitud,
        )
        try:
            async with eta_semaphore:
                estimate = await estimate_route(
                    route_estimator,
                    driver_location,
                    origin,
                    requested_vehicle,
                    timeout_seconds=route_timeout_seconds,
                )
        except (DependencyTimeoutError, DependencyUnavailableError):
            if not allow_eta_degradation:
                raise
            return candidate
        return candidate.model_copy(
            update={"eta_retiro_minutos": estimate.eta_minutos}
        )

    candidates = await asyncio.gather(*(add_eta(result) for result in selected))
    return ResultadoBusquedaConductores(
        conductores=list(candidates),
        radio_aplicado_km=radius_km,
        generado_en=current_time,
    )
