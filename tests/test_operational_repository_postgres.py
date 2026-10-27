from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import (
    EstadoOperativoORM,
    RegistroIdempotenciaORM,
    ReservaTemporalORM,
)
from app.repositories.operational import SqlAlchemyOperationalRepository


@pytest.fixture
def postgres_session() -> Iterator[Session]:
    if engine is None or engine.dialect.name != "postgresql":
        pytest.skip("Este test de integración requiere PostgreSQL.")
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _delete_test_rows(
    session: Session,
    *,
    conductor_id: UUID,
    record_id: UUID | None = None,
) -> None:
    with session.begin():
        session.execute(
            delete(EstadoOperativoORM).where(
                EstadoOperativoORM.conductor_id == conductor_id
            )
        )
        session.execute(
            delete(ReservaTemporalORM).where(
                ReservaTemporalORM.conductor_id == conductor_id
            )
        )
        if record_id is not None:
            session.execute(
                delete(RegistroIdempotenciaORM).where(
                    RegistroIdempotenciaORM.id == record_id
                )
            )


def test_postgres_repository_commits_state_and_reservation_together(
    postgres_session: Session,
) -> None:
    repository = SqlAlchemyOperationalRepository(postgres_session)
    conductor_id = uuid4()
    now = datetime.now(timezone.utc)
    state = EstadoOperativoORM(
        conductor_id=conductor_id,
        connected=True,
        available=True,
        recibido_en=now,
    )
    reservation = ReservaTemporalORM(
        conductor_id=conductor_id,
        solicitud_id=uuid4(),
        estado_temporal="RESERVADO",
        expira_en=now + timedelta(minutes=1),
    )

    try:
        with repository.transaction():
            repository.save_state(state)
            repository.save_reservation(reservation)

        assert repository.get_state(conductor_id) is not None
        assert repository.get_reservation(conductor_id, for_update=True) is not None
    finally:
        postgres_session.rollback()
        _delete_test_rows(postgres_session, conductor_id=conductor_id)


def test_postgres_repository_rolls_back_related_writes_on_constraint_failure(
    postgres_session: Session,
) -> None:
    repository = SqlAlchemyOperationalRepository(postgres_session)
    conductor_id = uuid4()
    actor_id = uuid4()
    record_id = uuid4()
    first_record = RegistroIdempotenciaORM(
        id=record_id,
        actor_id=actor_id,
        operacion="POST:/reserva",
        idempotency_key="rollback-key",
        body_hash="e" * 64,
        response_status=200,
        response_body={"ok": True},
    )
    duplicate_record = RegistroIdempotenciaORM(
        actor_id=actor_id,
        operacion="POST:/reserva",
        idempotency_key="rollback-key",
        body_hash="f" * 64,
        response_status=200,
        response_body={"duplicate": True},
    )

    try:
        with pytest.raises(IntegrityError):
            with repository.transaction():
                repository.save_state(
                    EstadoOperativoORM(
                        conductor_id=conductor_id,
                        connected=True,
                        available=True,
                    )
                )
                repository.save_idempotency_record(first_record)
                repository.save_idempotency_record(duplicate_record)

        assert repository.get_state(conductor_id) is None
        assert (
            repository.get_idempotency_record(
                actor_id=actor_id,
                operation="POST:/reserva",
                key="rollback-key",
            )
            is None
        )
    finally:
        postgres_session.rollback()
        _delete_test_rows(
            postgres_session,
            conductor_id=conductor_id,
            record_id=record_id,
        )
