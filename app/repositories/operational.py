from collections.abc import Generator
from contextlib import contextmanager
from typing import Self
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import (
    EstadoOperativoORM,
    EventoOperativoORM,
    RegistroIdempotenciaORM,
    ReservaTemporalORM,
)


class SqlAlchemyOperationalRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @contextmanager
    def transaction(self) -> Generator[Self, None, None]:
        with self._session.begin():
            yield self

    def get_state(self, conductor_id: UUID) -> EstadoOperativoORM | None:
        return self._session.get(EstadoOperativoORM, conductor_id)

    def list_available_states(self) -> list[EstadoOperativoORM]:
        statement = (
            select(EstadoOperativoORM)
            .where(
                EstadoOperativoORM.connected.is_(True),
                EstadoOperativoORM.available.is_(True),
            )
            .order_by(EstadoOperativoORM.conductor_id)
        )
        return list(self._session.scalars(statement))

    def save_state(self, state: EstadoOperativoORM) -> EstadoOperativoORM:
        stored = self._session.merge(state)
        self._session.flush()
        return stored

    def get_event(self, event_id: UUID) -> EventoOperativoORM | None:
        return self._session.get(EventoOperativoORM, event_id)

    def save_event(self, event: EventoOperativoORM) -> EventoOperativoORM:
        stored = self._session.merge(event)
        self._session.flush()
        return stored

    def lock_conductor(self, conductor_id: UUID) -> None:
        if (
            self._session.bind is not None
            and self._session.bind.dialect.name == "postgresql"
        ):
            self._lock_key(int.from_bytes(conductor_id.bytes[:8], "big", signed=True))

    def lock_event(self, event_id: UUID) -> None:
        if (
            self._session.bind is not None
            and self._session.bind.dialect.name == "postgresql"
        ):
            self._lock_key(int.from_bytes(event_id.bytes[:8], "big", signed=True))

    def _lock_key(self, lock_key: int) -> None:
        self._session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": lock_key},
        )

    def get_reservation(
        self, conductor_id: UUID, *, for_update: bool = False
    ) -> ReservaTemporalORM | None:
        statement = select(ReservaTemporalORM).where(
            ReservaTemporalORM.conductor_id == conductor_id
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def save_reservation(
        self, reservation: ReservaTemporalORM
    ) -> ReservaTemporalORM:
        stored = self._session.merge(reservation)
        self._session.flush()
        return stored

    def get_idempotency_record(
        self, *, actor_id: UUID, operation: str, key: str
    ) -> RegistroIdempotenciaORM | None:
        statement = select(RegistroIdempotenciaORM).where(
            RegistroIdempotenciaORM.actor_id == actor_id,
            RegistroIdempotenciaORM.operacion == operation,
            RegistroIdempotenciaORM.idempotency_key == key,
        )
        return self._session.scalar(statement)

    def save_idempotency_record(
        self, record: RegistroIdempotenciaORM
    ) -> RegistroIdempotenciaORM:
        stored = self._session.merge(record)
        self._session.flush()
        return stored
