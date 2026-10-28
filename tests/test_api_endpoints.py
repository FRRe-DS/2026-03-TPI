from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.auth import AuthenticatedPrincipal, get_authenticated_principal
from app.core.config import Settings
from app.core.errors import M3UnavailableError
from app.clients.m3 import ElegibilidadConductor, EstadoHabilitacionM3
from app.database import Base, SessionLocal, engine as database_engine, get_db
from app.main import create_app
from app.models import (
    EstadoOperativoORM,
    RegistroIdempotenciaORM,
    ReservaTemporalORM,
)
from app.repositories.dependencies import get_location_repository
from app.repositories.locations import (
    LocationWriteResult,
    StoredLocation,
)
from app.schemas.schemas import (
    ActualizarUbicacion,
    EstimacionRuta,
    FuenteEstimacion,
    PuntoGeografico,
    TipoVehiculo,
)
from app.servicios.coverage import CoverageArea
from redis.exceptions import ConnectionError as RedisConnectionError


class MemoryLocationRepository:
    def __init__(self) -> None:
        self.locations: dict[UUID, StoredLocation] = {}

    async def upsert(self, location: ActualizarUbicacion) -> LocationWriteResult:
        current = self.locations.get(location.conductor_id)
        if current is None:
            result = LocationWriteResult.CREATED
        elif location.timestamp_ubicacion < current.timestamp_ubicacion:
            return LocationWriteResult.STALE
        elif location.timestamp_ubicacion == current.timestamp_ubicacion:
            if (location.latitud, location.longitud) == (
                current.latitud,
                current.longitud,
            ):
                return LocationWriteResult.IDEMPOTENT
            return LocationWriteResult.CONFLICT
        else:
            result = LocationWriteResult.APPLIED

        received_at = datetime.now(timezone.utc)
        self.locations[location.conductor_id] = StoredLocation(
            conductor_id=location.conductor_id,
            latitud=location.latitud,
            longitud=location.longitud,
            timestamp_ubicacion=location.timestamp_ubicacion,
            recibida_en=received_at,
            expira_en=received_at + timedelta(seconds=30),
        )
        return result

    async def get_current(self, conductor_id: UUID) -> StoredLocation | None:
        return self.locations.get(conductor_id)


class NearbyM3Client:
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


def configure_nearby(application: FastAPI) -> MemoryLocationRepository:
    repository = MemoryLocationRepository()
    application.dependency_overrides[get_location_repository] = lambda: repository
    application.state.coverage = CoverageArea.from_geojson(
        '{"type":"Polygon","coordinates":'
        '[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}'
    )
    return repository


@pytest.fixture
def api() -> Iterator[tuple[TestClient, FastAPI]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    application = create_app(
        Settings(
            _env_file=None,
            redis_url=None,
            reservation_ttl_seconds=60,
        )
    )
    application.state.test_engine = engine
    principal = AuthenticatedPrincipal(subject=uuid4())
    application.dependency_overrides[get_authenticated_principal] = lambda: principal

    def override_db() -> Iterator[Session]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    application.dependency_overrides[get_db] = override_db
    application.dependency_overrides[get_location_repository] = (
        lambda: MemoryLocationRepository()
    )
    with TestClient(application) as client:
        yield client, application
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_location_endpoint_returns_create_then_update_without_coordinates(
    api: tuple[TestClient, object],
) -> None:
    client, application = api
    repository = MemoryLocationRepository()
    application.dependency_overrides[get_location_repository] = lambda: repository
    conductor_id = uuid4()
    payload = {
        "conductor_id": str(conductor_id),
        "latitud": -27.4512,
        "longitud": -58.9866,
        "timestamp_ubicacion": "2026-10-27T15:00:00Z",
    }

    first = client.post("/api/v1/ubicaciones", json=payload)
    assert first.status_code == 403
    application.dependency_overrides[get_authenticated_principal] = (
        lambda: AuthenticatedPrincipal(subject=conductor_id)
    )
    first = client.post("/api/v1/ubicaciones", json=payload)
    assert first.status_code == 201
    assert first.headers["x-request-id"]
    assert "latitud" not in first.json()
    assert "longitud" not in first.json()

    payload["timestamp_ubicacion"] = "2026-10-27T15:00:01Z"
    updated = client.post("/api/v1/ubicaciones", json=payload)
    assert updated.status_code == 200
    assert updated.json()["timestamp_ubicacion"] == payload["timestamp_ubicacion"]

    conflict_payload = {
        **payload,
        "timestamp_ubicacion": "2026-10-27T15:00:01Z",
        "latitud": -27.45,
    }
    conflict = client.post("/api/v1/ubicaciones", json=conflict_payload)
    assert conflict.status_code == 409
    latest = repository.locations[conductor_id]
    assert latest.latitud == -27.4512


def test_location_storage_failure_returns_service_unavailable(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, application = api
    conductor_id = uuid4()
    application.dependency_overrides[get_authenticated_principal] = (
        lambda: AuthenticatedPrincipal(subject=conductor_id)
    )

    class UnavailableRepository:
        async def upsert(self, location: ActualizarUbicacion) -> LocationWriteResult:
            raise RedisConnectionError("private connection detail")

        async def get_current(self, driver_id: UUID) -> None:
            return None

    application.dependency_overrides[get_location_repository] = (
        lambda: UnavailableRepository()
    )
    response = client.post(
        "/api/v1/ubicaciones",
        json={
            "conductor_id": str(conductor_id),
            "latitud": -27.4512,
            "longitud": -58.9866,
            "timestamp_ubicacion": "2026-10-27T15:00:00Z",
        },
    )
    assert response.status_code == 503
    assert "private connection detail" not in response.text


def test_location_timestamp_validation_uses_injected_clock(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, application = api
    repository = MemoryLocationRepository()
    conductor_id = uuid4()
    now = datetime(2026, 10, 20, 15, 4, 5, tzinfo=timezone.utc)
    application.state.clock = lambda: now
    application.dependency_overrides[get_location_repository] = lambda: repository
    application.dependency_overrides[get_authenticated_principal] = (
        lambda: AuthenticatedPrincipal(subject=conductor_id)
    )

    def post_location(timestamp: str):
        return client.post(
            "/api/v1/ubicaciones",
            json={
                "conductor_id": str(conductor_id),
                "latitud": -90,
                "longitud": 180,
                "timestamp_ubicacion": timestamp,
            },
        )

    accepted = post_location(now.isoformat().replace("+00:00", "Z"))
    assert accepted.status_code == 201
    assert accepted.headers["x-request-id"]

    future = post_location((now + timedelta(microseconds=1)).isoformat())
    assert future.status_code == 422
    assert future.headers["content-type"].startswith("application/problem+json")
    assert future.headers["x-request-id"]
    assert future.json()["code"] == "LOCATION_TIMESTAMP_IN_FUTURE"
    assert repository.locations[conductor_id].timestamp_ubicacion == now


def test_operational_state_normalizes_and_deduplicates_event_ids(
    api: tuple[TestClient, object],
) -> None:
    client, _ = api
    conductor_id = uuid4()
    event_id = uuid4()
    payload = {
        "event_id": str(event_id),
        "connected": False,
        "available": True,
        "timestamp_evento": "2026-10-27T15:00:00Z",
    }

    created = client.post(
        f"/api/v1/conductores/{conductor_id}/estado-operativo", json=payload
    )
    assert created.status_code == 201
    assert created.json()["available"] is False
    replay = client.post(
        f"/api/v1/conductores/{conductor_id}/estado-operativo", json=payload
    )
    assert replay.status_code == 200
    assert replay.json() == created.json()

    changed = {**payload, "available": False}
    conflict = client.post(
        f"/api/v1/conductores/{conductor_id}/estado-operativo", json=changed
    )
    assert conflict.status_code == 422
    assert conflict.headers["content-type"].startswith("application/problem+json")


def test_operational_state_rejects_out_of_order_timestamp(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, _ = api
    conductor_id = uuid4()
    path = f"/api/v1/conductores/{conductor_id}/estado-operativo"
    first = client.post(
        path,
        json={
            "connected": True,
            "available": True,
            "timestamp_evento": "2026-10-27T15:00:02Z",
        },
    )
    assert first.status_code == 201

    stale = client.post(
        path,
        json={
            "connected": False,
            "available": False,
            "timestamp_evento": "2026-10-27T15:00:01Z",
        },
    )
    assert stale.status_code == 409


def test_reservation_idempotency_conflicts_release_and_request_correlation(
    api: tuple[TestClient, object],
) -> None:
    client, application = api
    conductor_id = uuid4()
    request_id = str(uuid4())
    request_id = request_id.replace("-", ".")
    request_headers = {
        "Idempotency-Key": "reservation-request-1",
        "X-Request-Id": request_id,
    }
    request_payload = {
        "estado_temporal": "RESERVADO",
        "solicitud_id": str(uuid4()),
    }
    path = f"/api/v1/conductores/{conductor_id}/reserva"
    absent_driver = uuid4()
    absent_reservation = client.post(
        f"/api/v1/conductores/{absent_driver}/reserva",
        json=request_payload,
        headers={"Idempotency-Key": "reservation-unknown-driver"},
    )
    assert absent_reservation.status_code == 404

    unavailable_driver = uuid4()
    unavailable = client.post(
        f"/api/v1/conductores/{unavailable_driver}/estado-operativo",
        json={"connected": False, "available": True},
    )
    assert unavailable.status_code == 201
    ineligible_reservation = client.post(
        f"/api/v1/conductores/{unavailable_driver}/reserva",
        json=request_payload,
        headers={"Idempotency-Key": "reservation-unavailable-driver"},
    )
    assert ineligible_reservation.status_code == 409

    state_response = client.post(
        f"/api/v1/conductores/{conductor_id}/estado-operativo",
        json={"connected": True, "available": True},
    )
    assert state_response.status_code == 201

    created = client.post(path, json=request_payload, headers=request_headers)
    assert created.status_code == 201
    assert created.headers["x-request-id"] == request_id
    replay = client.post(path, json=request_payload, headers=request_headers)
    assert replay.status_code == 201
    assert replay.json() == created.json()
    repeated_request = client.post(
        path,
        json=request_payload,
        headers={"Idempotency-Key": "reservation-request-same-owner"},
    )
    assert repeated_request.status_code == 200
    assert repeated_request.json()["idempotente"] is True
    with Session(application.state.test_engine) as session:
        reservation_count = session.scalar(
            select(func.count())
            .select_from(ReservaTemporalORM)
            .where(ReservaTemporalORM.conductor_id == conductor_id)
        )
    assert reservation_count == 1

    changed_body = {**request_payload, "solicitud_id": str(uuid4())}
    reused_key = client.post(path, json=changed_body, headers=request_headers)
    assert reused_key.status_code == 422

    other_request = {
        "estado_temporal": "RESERVADO",
        "solicitud_id": str(uuid4()),
    }
    conflict = client.post(
        path,
        json=other_request,
        headers={"Idempotency-Key": "reservation-request-2"},
    )
    assert conflict.status_code == 409

    release = {
        "estado_temporal": "LIBERADO",
        "solicitud_id": request_payload["solicitud_id"],
    }
    released = client.post(
        path,
        json=release,
        headers={"Idempotency-Key": "reservation-release-1"},
    )
    assert released.status_code == 200
    assert released.json()["estado_temporal"] == "LIBERADO"

    owner_mismatch = client.post(
        path,
        json={
            "estado_temporal": "LIBERADO",
            "solicitud_id": str(uuid4()),
        },
        headers={"Idempotency-Key": "reservation-release-wrong-owner"},
    )
    assert owner_mismatch.status_code == 409
    missing_key = client.post(path, json=release)
    assert missing_key.status_code == 422


def test_expired_reservation_can_be_replaced_with_injected_clock(
    api: tuple[TestClient, object],
) -> None:
    client, application = api
    current_time = [datetime(2026, 10, 27, 15, 0, tzinfo=timezone.utc)]
    application.state.clock = lambda: current_time[0]
    conductor_id = uuid4()
    path = f"/api/v1/conductores/{conductor_id}/reserva"
    state_response = client.post(
        f"/api/v1/conductores/{conductor_id}/estado-operativo",
        json={"connected": True, "available": True},
    )
    assert state_response.status_code == 201
    first = client.post(
        path,
        json={"estado_temporal": "RESERVADO", "solicitud_id": str(uuid4())},
        headers={"Idempotency-Key": "clock-reservation-1"},
    )
    assert first.status_code == 201
    assert first.json()["expira_en"] == "2026-10-27T15:01:00Z"

    current_time[0] += timedelta(seconds=60)
    replacement = client.post(
        path,
        json={"estado_temporal": "RESERVADO", "solicitud_id": str(uuid4())},
        headers={"Idempotency-Key": "clock-reservation-2"},
    )
    assert replacement.status_code == 201


def test_route_estimation_uses_injected_provider_and_maps_timeout(
    api: tuple[TestClient, object],
) -> None:
    client, application = api
    calls: list[tuple[float, float, str | None]] = []

    async def estimator(origin, destination, vehicle):
        calls.append((origin.latitud, destination.longitud, vehicle.value if vehicle else None))
        return {
            "origen": origin.model_dump(),
            "destino": destination.model_dump(),
            "distancia_estimada_km": 6.8,
            "eta_minutos": 18,
            "calculado_en": "2026-10-27T15:00:00Z",
            "fuente": "proveedor_mapa",
        }

    application.state.route_estimator = estimator
    query = (
        "origen_latitud=-34.6037&origen_longitud=-58.3816"
        "&destino_latitud=-34.6158&destino_longitud=-58.4333&tipo_vehiculo=AUTO"
    )
    result = client.get(f"/api/v1/rutas/estimacion?{query}")
    assert result.status_code == 200
    assert result.json()["distancia_estimada_km"] == 6.8
    assert calls == [(-34.6037, -58.4333, "AUTO")]
    invalid_coordinates = client.get(
        f"/api/v1/rutas/estimacion?{query.replace('origen_latitud=-34.6037', 'origen_latitud=91')}"
    )
    assert invalid_coordinates.status_code == 422

    async def timeout_estimator(origin, destination, vehicle):
        raise TimeoutError

    application.state.route_estimator = timeout_estimator
    timed_out = client.get(f"/api/v1/rutas/estimacion?{query}")
    assert timed_out.status_code == 504
    assert timed_out.headers["content-type"].startswith("application/problem+json")

    application.state.route_estimator = None
    unavailable = client.get(f"/api/v1/rutas/estimacion?{query}")
    assert unavailable.status_code == 503

    async def failing_estimator(origin, destination, vehicle):
        raise httpx.ConnectError("private map provider detail")

    application.state.route_estimator = failing_estimator
    failed = client.get(f"/api/v1/rutas/estimacion?{query}")
    assert failed.status_code == 503
    assert "private map provider detail" not in failed.text


def test_nearby_endpoint_returns_eta_without_driver_coordinates(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, application = api
    driver_id = uuid4()
    location_repository = configure_nearby(application)
    now = application.state.clock()
    driver_latitude, driver_longitude = 0.5, 0.51
    location_repository.locations[driver_id] = StoredLocation(
        conductor_id=driver_id,
        latitud=driver_latitude,
        longitud=driver_longitude,
        timestamp_ubicacion=now,
        recibida_en=now,
        expira_en=now + timedelta(seconds=30),
    )
    with Session(application.state.test_engine) as session:
        session.add(
            EstadoOperativoORM(
                conductor_id=driver_id,
                connected=True,
                available=True,
                actualizado_en=now,
            )
        )
        session.commit()
    application.state.m3_client = NearbyM3Client(
        {
            driver_id: ElegibilidadConductor(
                estado_habilitacion=EstadoHabilitacionM3.APPROVED,
                tipos_vehiculo_habilitados=(TipoVehiculo.AUTO,),
            )
        }
    )
    route_calls: list[tuple[PuntoGeografico, PuntoGeografico]] = []

    async def estimator(origin, destination, vehicle):
        route_calls.append((origin, destination))
        assert vehicle is TipoVehiculo.AUTO
        return EstimacionRuta(
            origen=origin,
            destino=destination,
            distancia_estimada_km=1.2,
            eta_minutos=4,
            calculado_en=now,
            fuente=FuenteEstimacion.PROVEEDOR_MAPA,
        )

    application.state.route_estimator = estimator
    response = client.get(
        "/api/v1/conductores/cercanos?"
        "origen_latitud=0.5&origen_longitud=0.5&tipo_vehiculo=AUTO"
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["radio_aplicado_km"] == 5
    candidate = response.json()["conductores"][0]
    assert candidate["conductor_id"] == str(driver_id)
    assert candidate["eta_retiro_minutos"] == 4
    assert "latitud" not in candidate
    assert "longitud" not in candidate
    assert str(driver_latitude) not in response.text
    assert str(driver_longitude) not in response.text
    assert route_calls == [
        (
            PuntoGeografico(latitud=driver_latitude, longitud=driver_longitude),
            PuntoGeografico(latitud=0.5, longitud=0.5),
        )
    ]


def test_nearby_endpoint_returns_empty_list_and_privacy_header(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, application = api
    configure_nearby(application)
    application.state.m3_client = NearbyM3Client()

    response = client.get(
        "/api/v1/conductores/cercanos?"
        "origen_latitud=0.5&origen_longitud=0.5&tipo_vehiculo=AUTO"
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["conductores"] == []
    assert response.json()["radio_aplicado_km"] == 5


def test_nearby_endpoint_validates_search_radius_and_limit(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, application = api
    configure_nearby(application)
    application.state.m3_client = NearbyM3Client()
    base_query = (
        "origen_latitud=0.5&origen_longitud=0.5&tipo_vehiculo=AUTO"
    )

    for extra_query in (
        "radio_km=0",
        "radio_km=21",
        "radio_maximo_km=4",
        "radio_maximo_km=21",
        "limite=0",
        "limite=101",
    ):
        response = client.get(
            f"/api/v1/conductores/cercanos?{base_query}&{extra_query}"
        )
        assert response.status_code == 422, extra_query
        assert response.headers["cache-control"] == "no-store"


def test_nearby_endpoint_propagates_m3_failure_even_when_eta_can_degrade(
    api: tuple[TestClient, FastAPI],
) -> None:
    client, application = api
    driver_id = uuid4()
    location_repository = configure_nearby(application)
    now = application.state.clock()
    location_repository.locations[driver_id] = StoredLocation(
        conductor_id=driver_id,
        latitud=0.5,
        longitud=0.51,
        timestamp_ubicacion=now,
        recibida_en=now,
        expira_en=now + timedelta(seconds=30),
    )
    with Session(application.state.test_engine) as session:
        session.add(
            EstadoOperativoORM(
                conductor_id=driver_id,
                connected=True,
                available=True,
                actualizado_en=now,
            )
        )
        session.commit()
    application.state.m3_client = NearbyM3Client(error=M3UnavailableError())

    async def timed_out_estimator(*_):
        raise TimeoutError

    application.state.route_estimator = timed_out_estimator
    response = client.get(
        "/api/v1/conductores/cercanos?"
        "origen_latitud=0.5&origen_longitud=0.5&tipo_vehiculo=AUTO"
    )

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["code"] == "M3_UNAVAILABLE"


def test_missing_bearer_token_is_rejected_with_problem_details(
    api: tuple[TestClient, object],
) -> None:
    client, application = api
    application.dependency_overrides.pop(get_authenticated_principal)
    response = client.get(
        "/api/v1/rutas/estimacion?origen_latitud=0&origen_longitud=0"
        "&destino_latitud=1&destino_longitud=1"
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["content-type"].startswith("application/problem+json")
    invalid_token = client.get(
        "/api/v1/rutas/estimacion?origen_latitud=0&origen_longitud=0"
        "&destino_latitud=1&destino_longitud=1",
        headers={"Authorization": "Bearer unverified-token"},
    )
    assert invalid_token.status_code == 503


def test_reservation_is_atomic_for_concurrent_postgres_requests() -> None:
    if database_engine is None or database_engine.dialect.name != "postgresql":
        pytest.skip("Este test de concurrencia requiere PostgreSQL.")

    conductor_id = uuid4()
    principal = AuthenticatedPrincipal(subject=uuid4())
    application = create_app(
        Settings(_env_file=None, redis_url=None, reservation_ttl_seconds=60)
    )
    application.dependency_overrides[get_authenticated_principal] = lambda: principal
    path = f"/api/v1/conductores/{conductor_id}/reserva"

    with TestClient(application) as client:
        state_response = client.post(
            f"/api/v1/conductores/{conductor_id}/estado-operativo",
            json={"connected": True, "available": True},
        )
        assert state_response.status_code == 201

        def request_reservation(solicitud_id: str, key: str) -> int:
            response = client.post(
                path,
                json={
                    "estado_temporal": "RESERVADO",
                    "solicitud_id": solicitud_id,
                },
                headers={"Idempotency-Key": key},
            )
            return response.status_code

        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                responses = list(
                    executor.map(
                        lambda pair: request_reservation(*pair),
                        [
                            (str(uuid4()), "concurrent-reservation-1"),
                            (str(uuid4()), "concurrent-reservation-2"),
                        ],
                    )
                )
            assert sorted(responses) == [201, 409]
        finally:
            with SessionLocal.begin() as session:
                session.execute(
                    delete(EstadoOperativoORM).where(
                        EstadoOperativoORM.conductor_id == conductor_id
                    )
                )
                session.execute(
                    delete(RegistroIdempotenciaORM).where(
                        RegistroIdempotenciaORM.operacion
                        == f"reservation:{conductor_id}"
                    )
                )
                session.execute(
                    delete(ReservaTemporalORM).where(
                        ReservaTemporalORM.conductor_id == conductor_id
                    )
                )
