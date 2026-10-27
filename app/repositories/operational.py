from collections.abc import Generator
from contextlib import contextmanager
from typing import Self
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    EstadoOperativoORM,
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

    def save_state(self, state: EstadoOperativoORM) -> EstadoOperativoORM:
        stored = self._session.merge(state)
        self._session.flush()
        return stored

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
