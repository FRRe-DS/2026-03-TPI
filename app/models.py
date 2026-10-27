import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.database import Base


class UTCDateTime(TypeDecorator[datetime]):
    impl = DateTime
    cache_ok = True

    def __init__(self) -> None:
        super().__init__(timezone=True)

    def process_bind_param(
        self, value: datetime | None, _dialect: Any
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Los timestamps persistidos deben incluir zona horaria.")
        return value.astimezone(timezone.utc)

    def process_result_value(
        self, value: datetime | None, _dialect: Any
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class EstadoOperativoORM(Base):
    __tablename__ = "estado_operativo"
    __table_args__ = (
        CheckConstraint(
            "connected = true OR available = false",
            name="ck_estado_operativo_available_requires_connection",
        ),
    )

    conductor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=True
    )
    connected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actualizado_en: Mapped[datetime | None] = mapped_column(UTCDateTime())
    recibido_en: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class EventoOperativoORM(Base):
    __tablename__ = "eventos_operativos"
    __table_args__ = (
        CheckConstraint(
            "length(body_hash) = 64", name="ck_evento_operativo_hash_sha256"
        ),
        CheckConstraint(
            "response_status BETWEEN 100 AND 599",
            name="ck_evento_operativo_response_status",
        ),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    conductor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    body_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    recibido_en: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class ReservaTemporalORM(Base):
    __tablename__ = "reservas_temporales"
    __table_args__ = (
        CheckConstraint(
            "estado_temporal IN ('RESERVADO', 'LIBERADO')",
            name="ck_reserva_estado_temporal",
        ),
        CheckConstraint(
            "estado_temporal != 'RESERVADO' OR expira_en IS NOT NULL",
            name="ck_reserva_activa_requiere_expiracion",
        ),
    )

    conductor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True
    )
    solicitud_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    estado_temporal: Mapped[str] = mapped_column(String(16), nullable=False)
    creada_en: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    expira_en: Mapped[datetime | None] = mapped_column(UTCDateTime())


class RegistroIdempotenciaORM(Base):
    __tablename__ = "registros_idempotencia"
    __table_args__ = (
        UniqueConstraint(
            "actor_id",
            "operacion",
            "idempotency_key",
            name="uq_idempotencia_actor_operacion_key",
        ),
        CheckConstraint(
            "length(body_hash) = 64", name="ck_idempotencia_hash_sha256"
        ),
        CheckConstraint(
            "response_status BETWEEN 100 AND 599",
            name="ck_idempotencia_response_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    operacion: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    body_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    expira_en: Mapped[datetime | None] = mapped_column(UTCDateTime())
