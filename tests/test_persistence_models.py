from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.database import get_db
from app.models import (
    EstadoOperativoORM,
    RegistroIdempotenciaORM,
    ReservaTemporalORM,
)
from app.repositories.dependencies import get_operational_repository
from app.repositories.operational import SqlAlchemyOperationalRepository
from app.repositories.dependencies import get_operational_repository
from app.schemas.schemas import EstadoOperativoRegistrado, ResultadoReservaTemporal


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_operational_state_crud_and_pydantic_from_attributes(
    db_session: Session,
) -> None:
    conductor_id = uuid4()
    event_id = uuid4()
    received_at = datetime(2026, 10, 27, 21, 0, tzinfo=timezone.utc)
    state = EstadoOperativoORM(
        conductor_id=conductor_id,
        event_id=event_id,
        connected=True,
        available=True,
        actualizado_en=received_at,
        recibido_en=received_at,
    )

    db_session.add(state)
    db_session.commit()
    db_session.expire_all()
    stored = db_session.get(EstadoOperativoORM, conductor_id)

    assert stored is not None
    assert stored.event_id == event_id
    assert stored.recibido_en == received_at
    response = EstadoOperativoRegistrado.model_validate(stored)
    assert response.conductor_id == conductor_id
    assert response.event_id == event_id
    assert response.available is True

    stored.available = False
    db_session.commit()
    assert db_session.get(EstadoOperativoORM, conductor_id).available is False

    db_session.delete(stored)
    db_session.commit()
    assert db_session.get(EstadoOperativoORM, conductor_id) is None


def test_operational_state_rejects_available_when_disconnected(
    db_session: Session,
) -> None:
    db_session.add(
        EstadoOperativoORM(
            conductor_id=uuid4(),
            connected=False,
            available=True,
            recibido_en=datetime.now(timezone.utc),
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_persistence_timestamp_defaults_are_utc(db_session: Session) -> None:
    state = EstadoOperativoORM(
        conductor_id=uuid4(), connected=True, available=False
    )
    reservation = ReservaTemporalORM(
        conductor_id=uuid4(),
        solicitud_id=uuid4(),
        estado_temporal="LIBERADO",
    )
    db_session.add_all([state, reservation])
    db_session.commit()
    db_session.expire_all()

    stored_state = db_session.get(EstadoOperativoORM, state.conductor_id)
    stored_reservation = db_session.get(
        ReservaTemporalORM, reservation.conductor_id
    )
    assert stored_state is not None
    assert stored_reservation is not None
    assert stored_state.recibido_en.utcoffset() == timedelta(0)
    assert stored_reservation.creada_en.utcoffset() == timedelta(0)
    assert stored_reservation.actualizado_en.utcoffset() == timedelta(0)


def test_reservation_crud_and_pydantic_from_attributes(db_session: Session) -> None:
    conductor_id = uuid4()
    solicitud_id = uuid4()
    now = datetime.now(timezone.utc)
    reservation = ReservaTemporalORM(
        conductor_id=conductor_id,
        solicitud_id=solicitud_id,
        estado_temporal="RESERVADO",
        creada_en=now,
        actualizado_en=now,
        expira_en=now + timedelta(minutes=5),
    )

    db_session.add(reservation)
    db_session.commit()
    db_session.expire_all()
    stored = db_session.get(ReservaTemporalORM, conductor_id)

    assert stored is not None
    response = ResultadoReservaTemporal.model_validate(stored)
    assert response.conductor_id == conductor_id
    assert response.solicitud_id == solicitud_id
    assert response.estado_temporal.value == "RESERVADO"
    assert response.expira_en == now + timedelta(minutes=5)

    stored.estado_temporal = "LIBERADO"
    stored.expira_en = None
    db_session.commit()
    assert (
        db_session.get(ReservaTemporalORM, conductor_id).estado_temporal
        == "LIBERADO"
    )

    db_session.delete(stored)
    db_session.commit()
    assert db_session.get(ReservaTemporalORM, conductor_id) is None


def test_reservation_requires_expiration_while_reserved(db_session: Session) -> None:
    db_session.add(
        ReservaTemporalORM(
            conductor_id=uuid4(),
            solicitud_id=uuid4(),
            estado_temporal="RESERVADO",
            actualizado_en=datetime.now(timezone.utc),
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_reservation_primary_key_prevents_two_rows_per_driver(
    db_session: Session,
) -> None:
    conductor_id = uuid4()
    now = datetime.now(timezone.utc)
    db_session.add(
        ReservaTemporalORM(
            conductor_id=conductor_id,
            solicitud_id=uuid4(),
            estado_temporal="LIBERADO",
            actualizado_en=now,
        )
    )
    db_session.commit()
    db_session.add(
        ReservaTemporalORM(
            conductor_id=conductor_id,
            solicitud_id=uuid4(),
            estado_temporal="RESERVADO",
            actualizado_en=now,
            expira_en=now + timedelta(minutes=1),
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_idempotency_record_crud_and_unique_scope(db_session: Session) -> None:
    actor_id = uuid4()
    record = RegistroIdempotenciaORM(
        actor_id=actor_id,
        operacion="POST:/api/v1/conductores/{conductor_id}/reserva",
        idempotency_key="reserve-key-1",
        body_hash="a" * 64,
        response_status=200,
        response_body={"estado_temporal": "RESERVADO"},
        expira_en=datetime.now(timezone.utc) + timedelta(days=1),
    )

    db_session.add(record)
    db_session.commit()
    stored = db_session.scalar(
        select(RegistroIdempotenciaORM).where(
            RegistroIdempotenciaORM.actor_id == actor_id,
            RegistroIdempotenciaORM.operacion == record.operacion,
            RegistroIdempotenciaORM.idempotency_key == record.idempotency_key,
        )
    )

    assert stored is not None
    assert stored.response_body == {"estado_temporal": "RESERVADO"}
    assert stored.response_status == 200
    stored.response_status = 201
    db_session.commit()
    assert db_session.get(RegistroIdempotenciaORM, record.id).response_status == 201

    duplicate = RegistroIdempotenciaORM(
        actor_id=actor_id,
        operacion=record.operacion,
        idempotency_key=record.idempotency_key,
        body_hash="b" * 64,
        response_status=200,
        response_body={},
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_models_do_not_persist_gps_or_candidate_projection() -> None:
    assert set(Base.metadata.tables) == {
        "estado_operativo",
        "eventos_operativos",
        "reservas_temporales",
        "registros_idempotencia",
    }


def test_operational_repository_commits_changes_as_one_transaction(
    db_session: Session,
) -> None:
    repository = SqlAlchemyOperationalRepository(db_session)
    state = EstadoOperativoORM(
        conductor_id=uuid4(), connected=True, available=True
    )
    reservation = ReservaTemporalORM(
        conductor_id=state.conductor_id,
        solicitud_id=uuid4(),
        estado_temporal="RESERVADO",
        expira_en=datetime.now(timezone.utc) + timedelta(minutes=2),
    )

    with repository.transaction():
        repository.save_state(state)
        repository.save_reservation(reservation)

    assert repository.get_state(state.conductor_id) is not None
    assert repository.get_reservation(state.conductor_id) is not None


def test_operational_repository_rolls_back_all_changes_on_failure(
    db_session: Session,
) -> None:
    repository = SqlAlchemyOperationalRepository(db_session)
    state = EstadoOperativoORM(
        conductor_id=uuid4(), connected=True, available=True
    )
    actor_id = uuid4()
    idempotency_record = RegistroIdempotenciaORM(
        actor_id=actor_id,
        operacion="POST:/reserva",
        idempotency_key="atomic-key",
        body_hash="c" * 64,
        response_status=200,
        response_body={"ok": True},
    )
    duplicate_key = RegistroIdempotenciaORM(
        actor_id=actor_id,
        operacion="POST:/reserva",
        idempotency_key="atomic-key",
        body_hash="d" * 64,
        response_status=200,
        response_body={"duplicate": True},
    )

    with pytest.raises(IntegrityError):
        with repository.transaction():
            repository.save_state(state)
            repository.save_idempotency_record(idempotency_record)
            repository.save_idempotency_record(duplicate_key)

    assert repository.get_state(state.conductor_id) is None
    assert (
        repository.get_idempotency_record(
            actor_id=actor_id, operation="POST:/reserva", key="atomic-key"
        )
        is None
    )


def test_operational_repository_is_injected_with_database_session(
    db_session: Session,
) -> None:
    conductor_id = uuid4()
    db_session.add(
        EstadoOperativoORM(
            conductor_id=conductor_id,
            connected=True,
            available=False,
        )
    )
    db_session.commit()
    application = FastAPI()

    def override_database_session() -> Session:
        return db_session

    application.dependency_overrides[get_db] = override_database_session

    @application.get("/test-state/{conductor_id}")
    def read_state(
        conductor_id: UUID,
        repository: SqlAlchemyOperationalRepository = Depends(
            get_operational_repository
        ),
    ) -> dict[str, bool]:
        state = repository.get_state(conductor_id)
        return {
            "found": state is not None,
            "connected": bool(state and state.connected),
        }

    with TestClient(application) as client:
        response = client.get(f"/test-state/{conductor_id}")

    assert response.status_code == 200
    assert response.json() == {"found": True, "connected": True}
