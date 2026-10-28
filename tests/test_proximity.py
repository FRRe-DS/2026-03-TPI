import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.clients.m3 import (
    ElegibilidadConductor,
    EstadoHabilitacionM3,
)
from app.core.errors import (
    DependencyTimeoutError,
    DomainError,
    M3UnavailableError,
)
from app.database import Base
from app.models import EstadoOperativoORM, ReservaTemporalORM
from app.repositories.locations import StoredLocation
from app.repositories.operational import SqlAlchemyOperationalRepository
from app.schemas.schemas import (
    EstimacionRuta,
    FuenteEstimacion,
    PuntoGeografico,
    TipoVehiculo,
)
from app.servicios.coverage import CoverageArea, require_coverage
from app.servicios.proximity import (
    EARTH_RADIUS_KM,
    find_nearby_candidates,
    linear_distance_km,
)

NOW = datetime(2026, 10, 27, 15, 4, 5, tzinfo=timezone.utc)
COVERAGE_GEOJSON = (
    '{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}'
)
AREA = CoverageArea.from_geojson(COVERAGE_GEOJSON)
ORIGIN = PuntoGeografico(latitud=0.5, longitud=0.5)


class FakeLocationRepository:
    def __init__(self, locations: dict[UUID, StoredLocation]) -> None:
        self.locations = locations

    async def get_current(self, conductor_id: UUID) -> StoredLocation | None:
        return self.locations.get(conductor_id)


class FakeM3Client:
    def __init__(
        self,
        eligibility: dict[UUID, ElegibilidadConductor] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.eligibility = eligibility or {}
        self.error = error
        self.calls: list[UUID] = []

    async def get_eligibility(self, conductor_id: UUID) -> ElegibilidadConductor:
        self.calls.append(conductor_id)
        if self.error is not None:
            raise self.error
        return self.eligibility[conductor_id]


def stored_location(
    conductor_id: UUID,
    latitude: float = 0.5,
    longitude: float = 0.6,
    expires_at: datetime = NOW + timedelta(seconds=30),
) -> StoredLocation:
    return StoredLocation(
        conductor_id=conductor_id,
        latitud=latitude,
        longitud=longitude,
        timestamp_ubicacion=NOW,
        recibida_en=NOW,
        expira_en=expires_at,
    )


def create_database() -> tuple[object, Session, SqlAlchemyOperationalRepository]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    return engine, session, SqlAlchemyOperationalRepository(session)


def add_driver(
    session: Session,
    conductor_id: UUID,
    *,
    connected: bool = True,
    available: bool = True,
) -> None:
    session.add(
        EstadoOperativoORM(
            conductor_id=conductor_id,
            connected=connected,
            available=available,
            actualizado_en=NOW,
        )
    )
    session.commit()


def approved(vehicle: TipoVehiculo = TipoVehiculo.AUTO) -> ElegibilidadConductor:
    return ElegibilidadConductor(
        estado_habilitacion=EstadoHabilitacionM3.APPROVED,
        tipos_vehiculo_habilitados=(vehicle,),
    )


def test_linear_distance_matches_known_equatorial_distance() -> None:
    origin = PuntoGeografico(latitud=0, longitud=0)
    location = stored_location(UUID(int=1), latitude=0, longitude=1)

    assert linear_distance_km(origin, location) == pytest.approx(
        EARTH_RADIUS_KM * 2 * 3.141592653589793 / 360,
        rel=1e-10,
    )


def test_coverage_includes_interior_and_boundary_but_excludes_exterior() -> None:
    assert AREA.covers(PuntoGeografico(latitud=0.5, longitud=0.5))
    assert AREA.covers(PuntoGeografico(latitud=0.5, longitud=1))
    assert not AREA.covers(PuntoGeografico(latitud=1.01, longitud=0.5))


def test_coverage_hole_excludes_interior_but_includes_its_boundary() -> None:
    area = CoverageArea.from_geojson(
        '{"type":"Polygon","coordinates":['
        '[[0,0],[4,0],[4,4],[0,4],[0,0]],'
        '[[1,1],[3,1],[3,3],[1,3],[1,1]]]}'
    )

    assert not area.covers(PuntoGeografico(latitud=2, longitud=2))
    assert area.covers(PuntoGeografico(latitud=1, longitud=2))


def test_coverage_requires_geometry_and_rejects_outside_search_origin() -> None:
    with pytest.raises(DomainError) as missing:
        require_coverage(None, ORIGIN)
    assert missing.value.status_code == 503

    with pytest.raises(DomainError) as outside:
        require_coverage(AREA, PuntoGeografico(latitud=2, longitud=2))
    assert outside.value.code == "LOCATION_OUTSIDE_COVERAGE"


def test_nearby_filter_returns_approved_available_and_current_driver_without_gps() -> None:
    driver_id = UUID("018f1f20-7b4a-7cc2-9d41-66382a18cc5a")
    engine, session, repository = create_database()
    try:
        add_driver(session, driver_id)
        m3 = FakeM3Client({driver_id: approved()})

        result = asyncio.run(
            find_nearby_candidates(
                origin=ORIGIN,
                requested_vehicle=TipoVehiculo.AUTO,
                radius_km=20,
                limit=20,
                max_radius_km=20,
                max_limit=20,
                location_repository=FakeLocationRepository(
                    {driver_id: stored_location(driver_id)}
                ),
                operational_repository=repository,
                m3_client=m3,
                coverage=AREA,
                now=NOW,
            )
        )

        assert [candidate.conductor_id for candidate in result.conductores] == [
            driver_id
        ]
        assert result.conductores[0].distancia_origen_km == pytest.approx(
            11.1195, rel=1e-3
        )
        assert "latitud" not in result.model_dump(mode="json")["conductores"][0]
        assert "longitud" not in result.model_dump(mode="json")["conductores"][0]
    finally:
        session.close()
        engine.dispose()


@pytest.mark.parametrize(
    ("location_factory", "reservation", "eligibility", "expected_m3_calls"),
    [
        ("expired", False, "approved", 0),
        ("outside_coverage", False, "approved", 0),
        ("current", True, "approved", 0),
        ("current", False, "rejected", 1),
        ("current", False, "wrong_vehicle", 1),
    ],
)
def test_nearby_filter_excludes_each_ineligible_driver(
    location_factory: str,
    reservation: bool,
    eligibility: str,
    expected_m3_calls: int,
) -> None:
    driver_id = UUID("018f1f20-7b4a-7cc2-9d41-66382a18cc5a")
    engine, session, repository = create_database()
    try:
        add_driver(session, driver_id)
        if reservation:
            session.add(
                ReservaTemporalORM(
                    conductor_id=driver_id,
                    solicitud_id=UUID("018f1f20-a128-739e-8af1-4caa35108a91"),
                    estado_temporal="RESERVADO",
                    creada_en=NOW,
                    actualizado_en=NOW,
                    expira_en=NOW + timedelta(minutes=1),
                )
            )
            session.commit()
        if location_factory == "expired":
            location = stored_location(driver_id, expires_at=NOW)
        elif location_factory == "outside_coverage":
            location = stored_location(driver_id, latitude=2, longitude=2)
        else:
            location = stored_location(driver_id)

        driver_eligibility = (
            approved()
            if eligibility == "approved"
            else ElegibilidadConductor(
                estado_habilitacion=EstadoHabilitacionM3.REJECTED,
                tipos_vehiculo_habilitados=(TipoVehiculo.AUTO,),
            )
            if eligibility == "rejected"
            else approved(TipoVehiculo.MOTO)
        )
        m3 = FakeM3Client({driver_id: driver_eligibility})

        result = asyncio.run(
            find_nearby_candidates(
                origin=ORIGIN,
                requested_vehicle=TipoVehiculo.AUTO,
                radius_km=20,
                limit=20,
                max_radius_km=20,
                max_limit=20,
                location_repository=FakeLocationRepository({driver_id: location}),
                operational_repository=repository,
                m3_client=m3,
                coverage=AREA,
                now=NOW,
            )
        )

        assert result.conductores == []
        assert len(m3.calls) == expected_m3_calls
    finally:
        session.close()
        engine.dispose()


def test_nearby_filter_applies_radius_limit_and_deterministic_order() -> None:
    nearest_id = UUID("018f1f20-7b4a-7cc2-9d41-66382a18cc5a")
    tied_id = UUID("018f1f20-a128-739e-8af1-4caa35108a91")
    tied_lower_id = UUID("018f1f20-a128-739e-8af1-4caa35108a90")
    farther_id = UUID("018f1f20-b128-739e-8af1-4caa35108a91")
    engine, session, repository = create_database()
    try:
        for driver_id in (farther_id, tied_id, tied_lower_id, nearest_id):
            add_driver(session, driver_id)
        locations = {
            nearest_id: stored_location(nearest_id, longitude=0.51),
            tied_id: stored_location(tied_id, longitude=0.52),
            tied_lower_id: stored_location(tied_lower_id, longitude=0.52),
            farther_id: stored_location(farther_id, longitude=0.53),
        }
        client = FakeM3Client(
            {driver_id: approved() for driver_id in locations}
        )

        result = asyncio.run(
            find_nearby_candidates(
                origin=ORIGIN,
                requested_vehicle=TipoVehiculo.AUTO,
                radius_km=2.3,
                limit=2,
                max_radius_km=20,
                max_limit=20,
                location_repository=FakeLocationRepository(locations),
                operational_repository=repository,
                m3_client=client,
                coverage=AREA,
                now=NOW,
            )
        )

        assert [candidate.conductor_id for candidate in result.conductores] == [
            nearest_id,
            tied_lower_id,
        ]
    finally:
        session.close()
        engine.dispose()


def test_nearby_filter_rejects_radius_and_limit_above_configuration() -> None:
    engine, session, repository = create_database()
    common = {
        "origin": ORIGIN,
        "requested_vehicle": TipoVehiculo.AUTO,
        "location_repository": FakeLocationRepository({}),
        "operational_repository": repository,
        "m3_client": FakeM3Client(),
        "coverage": AREA,
        "now": NOW,
    }
    try:
        with pytest.raises(DomainError) as invalid_radius:
            asyncio.run(
                find_nearby_candidates(
                    **common,
                    radius_km=20.1,
                    limit=20,
                    max_radius_km=20,
                    max_limit=20,
                )
            )
        assert invalid_radius.value.code == "INVALID_SEARCH_RADIUS"

        with pytest.raises(DomainError) as invalid_limit:
            asyncio.run(
                find_nearby_candidates(
                    **common,
                    radius_km=5,
                    limit=21,
                    max_radius_km=20,
                    max_limit=20,
                )
            )
        assert invalid_limit.value.code == "INVALID_SEARCH_LIMIT"
    finally:
        session.close()
        engine.dispose()


def test_candidate_at_exact_radius_boundary_is_included() -> None:
    driver_id = UUID("018f1f20-7b4a-7cc2-9d41-66382a18cc5a")
    driver_location = stored_location(driver_id, longitude=0.51)
    exact_distance = linear_distance_km(ORIGIN, driver_location)
    engine, session, repository = create_database()
    try:
        add_driver(session, driver_id)
        result = asyncio.run(
            find_nearby_candidates(
                origin=ORIGIN,
                requested_vehicle=TipoVehiculo.AUTO,
                radius_km=exact_distance,
                limit=20,
                max_radius_km=20,
                max_limit=20,
                location_repository=FakeLocationRepository(
                    {driver_id: driver_location}
                ),
                operational_repository=repository,
                m3_client=FakeM3Client({driver_id: approved()}),
                coverage=AREA,
                now=NOW,
            )
        )

        assert [candidate.conductor_id for candidate in result.conductores] == [
            driver_id
        ]
    finally:
        session.close()
        engine.dispose()


def test_unavailable_operational_state_is_not_considered_or_sent_to_m3() -> None:
    driver_id = UUID("018f1f20-7b4a-7cc2-9d41-66382a18cc5a")
    engine, session, repository = create_database()
    try:
        add_driver(session, driver_id, connected=False, available=False)
        m3 = FakeM3Client()

        result = asyncio.run(
            find_nearby_candidates(
                origin=ORIGIN,
                requested_vehicle=TipoVehiculo.AUTO,
                radius_km=20,
                limit=20,
                max_radius_km=20,
                max_limit=20,
                location_repository=FakeLocationRepository(
                    {driver_id: stored_location(driver_id)}
                ),
                operational_repository=repository,
                m3_client=m3,
                coverage=AREA,
                now=NOW,
            )
        )

        assert result.conductores == []
        assert m3.calls == []
    finally:
        session.close()
        engine.dispose()


def test_nearby_filter_propagates_m3_errors_instead_of_returning_empty() -> None:
    driver_id = UUID("018f1f20-7b4a-7cc2-9d41-66382a18cc5a")
    engine, session, repository = create_database()
    try:
        add_driver(session, driver_id)

        async def route_must_not_be_called(*_):
            raise AssertionError("M3 debe validar antes de consultar rutas.")

        with pytest.raises(M3UnavailableError):
            asyncio.run(
                find_nearby_candidates(
                    origin=ORIGIN,
                    requested_vehicle=TipoVehiculo.AUTO,
                    radius_km=20,
                    limit=20,
                    max_radius_km=20,
                    max_limit=20,
                    location_repository=FakeLocationRepository(
                        {driver_id: stored_location(driver_id)}
                    ),
                    operational_repository=repository,
                    m3_client=FakeM3Client(error=M3UnavailableError()),
                    coverage=AREA,
                    route_estimator=route_must_not_be_called,
                    allow_eta_degradation=True,
                    now=NOW,
                )
            )
    finally:
        session.close()
        engine.dispose()


def test_nearby_filter_adds_route_eta_from_driver_to_origin() -> None:
    driver_id = UUID("018f1f20-7b4a-7cc2-9d41-66382a18cc5a")
    driver_location = stored_location(driver_id, longitude=0.51)
    engine, session, repository = create_database()
    route_calls: list[tuple[PuntoGeografico, PuntoGeografico]] = []
    try:
        add_driver(session, driver_id)

        async def route_estimator(origin, destination, vehicle):
            route_calls.append((origin, destination))
            assert vehicle is TipoVehiculo.AUTO
            return EstimacionRuta(
                origen=origin,
                destino=destination,
                distancia_estimada_km=1.2,
                eta_minutos=4,
                calculado_en=NOW,
                fuente=FuenteEstimacion.PROVEEDOR_MAPA,
            )

        result = asyncio.run(
            find_nearby_candidates(
                origin=ORIGIN,
                requested_vehicle=TipoVehiculo.AUTO,
                radius_km=20,
                limit=20,
                max_radius_km=20,
                max_limit=20,
                location_repository=FakeLocationRepository(
                    {driver_id: driver_location}
                ),
                operational_repository=repository,
                m3_client=FakeM3Client({driver_id: approved()}),
                coverage=AREA,
                route_estimator=route_estimator,
                now=NOW,
            )
        )

        candidate = result.conductores[0]
        assert candidate.eta_retiro_minutos == 4
        assert route_calls == [
            (
                PuntoGeografico(latitud=0.5, longitud=0.51),
                ORIGIN,
            )
        ]
    finally:
        session.close()
        engine.dispose()


def test_nearby_filter_degrades_only_map_failures_when_policy_allows() -> None:
    driver_id = UUID("018f1f20-7b4a-7cc2-9d41-66382a18cc5a")
    engine, session, repository = create_database()
    try:
        add_driver(session, driver_id)

        async def timed_out_estimator(*_):
            raise TimeoutError

        result = asyncio.run(
            find_nearby_candidates(
                origin=ORIGIN,
                requested_vehicle=TipoVehiculo.AUTO,
                radius_km=20,
                limit=20,
                max_radius_km=20,
                max_limit=20,
                location_repository=FakeLocationRepository(
                    {driver_id: stored_location(driver_id)}
                ),
                operational_repository=repository,
                m3_client=FakeM3Client({driver_id: approved()}),
                coverage=AREA,
                route_estimator=timed_out_estimator,
                allow_eta_degradation=True,
                now=NOW,
            )
        )
        assert len(result.conductores) == 1
        assert result.conductores[0].eta_retiro_minutos is None

        with pytest.raises(DependencyTimeoutError):
            asyncio.run(
                find_nearby_candidates(
                    origin=ORIGIN,
                    requested_vehicle=TipoVehiculo.AUTO,
                    radius_km=20,
                    limit=20,
                    max_radius_km=20,
                    max_limit=20,
                    location_repository=FakeLocationRepository(
                        {driver_id: stored_location(driver_id)}
                    ),
                    operational_repository=repository,
                    m3_client=FakeM3Client({driver_id: approved()}),
                    coverage=AREA,
                    route_estimator=timed_out_estimator,
                    allow_eta_degradation=False,
                    now=NOW,
                )
            )
    finally:
        session.close()
        engine.dispose()
