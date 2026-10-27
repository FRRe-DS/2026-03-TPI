import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from redis.exceptions import RedisError

from app.core.auth import AuthenticatedPrincipal
from app.core.errors import DependencyUnavailableError, DomainError
from app.models import (
    EstadoOperativoORM,
    EventoOperativoORM,
    RegistroIdempotenciaORM,
    ReservaTemporalORM,
)
from app.repositories.locations import (
    LocationRepository,
    LocationWriteResult,
)
from app.repositories.operational import SqlAlchemyOperationalRepository
from app.schemas.schemas import (
    ActualizarUbicacion,
    CambioReservaTemporal,
    EstadoOperativo,
    EstadoOperativoRegistrado,
    EstadoTemporal,
    ResultadoReservaTemporal,
    UbicacionRegistrada,
)


def _hash_payload(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def register_location(
    repository: LocationRepository,
    location: ActualizarUbicacion,
    *,
    now: datetime,
) -> tuple[UbicacionRegistrada, int]:
    if location.timestamp_ubicacion > now:
        raise DomainError(
            status_code=422,
            code="LOCATION_TIMESTAMP_IN_FUTURE",
            title="Ubicación no procesable",
            detail="timestamp_ubicacion no puede ser posterior al momento actual.",
        )

    try:
        result = await repository.upsert(location)
        stored = await repository.get_current(location.conductor_id)
    except RedisError as error:
        raise DependencyUnavailableError(
            "El almacenamiento temporal de ubicaciones no está disponible."
        ) from error
    if result in (LocationWriteResult.STALE, LocationWriteResult.CONFLICT):
        raise DomainError(
            status_code=409,
            code="LOCATION_TIMESTAMP_CONFLICT",
            title="Conflicto de ubicación",
            detail=(
                "La actualización es anterior a la ubicación vigente o reutiliza "
                "su timestamp con coordenadas distintas."
            ),
        )

    if stored is None:
        raise RuntimeError("Redis no conservó la ubicación recién escrita.")
    response = UbicacionRegistrada(
        conductor_id=stored.conductor_id,
        timestamp_ubicacion=stored.timestamp_ubicacion,
        recibida_en=stored.recibida_en,
        vigente=True,
        expira_en=stored.expira_en,
    )
    return response, 201 if result is LocationWriteResult.CREATED else 200


def register_operational_state(
    repository: SqlAlchemyOperationalRepository,
    conductor_id: UUID,
    event: EstadoOperativo,
    *,
    now: datetime | None = None,
) -> tuple[EstadoOperativoRegistrado, int]:
    received_at = now or datetime.now(timezone.utc)
    body_hash = _hash_payload(
        {
            "conductor_id": str(conductor_id),
            **event.model_dump(mode="json"),
        }
    )

    with repository.transaction():
        repository.lock_conductor(conductor_id)
        if event.event_id is not None:
            repository.lock_event(event.event_id)
            previous_event = repository.get_event(event.event_id)
            if previous_event is not None:
                if previous_event.body_hash != body_hash:
                    raise DomainError(
                        status_code=422,
                        code="EVENT_ID_REUSED",
                        title="Evento no procesable",
                        detail="event_id ya fue utilizado con un cuerpo distinto.",
                    )
                return (
                    EstadoOperativoRegistrado.model_validate(
                        previous_event.response_body
                    ),
                    200,
                )

        current = repository.get_state(conductor_id)
        normalized_available = event.connected and event.available
        if (
            current is not None
            and event.timestamp_evento is not None
            and current.actualizado_en is not None
        ):
            if event.timestamp_evento < current.actualizado_en:
                raise DomainError(
                    status_code=409,
                    code="OUT_OF_ORDER_EVENT",
                    title="Conflicto de estado operativo",
                    detail="El evento es anterior al estado operativo vigente.",
                )
            if (
                event.timestamp_evento == current.actualizado_en
                and (
                    event.connected != current.connected
                    or normalized_available != current.available
                )
            ):
                raise DomainError(
                    status_code=409,
                    code="EVENT_TIMESTAMP_CONFLICT",
                    title="Conflicto de estado operativo",
                    detail="El timestamp del evento ya corresponde a otro estado.",
                )

        is_new = current is None
        state = EstadoOperativoORM(
            conductor_id=conductor_id,
            event_id=event.event_id,
            connected=event.connected,
            available=normalized_available,
            actualizado_en=event.timestamp_evento,
            recibido_en=received_at,
        )
        stored = repository.save_state(state)
        response = EstadoOperativoRegistrado.model_validate(stored)
        status_code = 201 if is_new else 200

        if event.event_id is not None:
            repository.save_event(
                EventoOperativoORM(
                    event_id=event.event_id,
                    conductor_id=conductor_id,
                    body_hash=body_hash,
                    response_status=status_code,
                    response_body=response.model_dump(mode="json"),
                    recibido_en=received_at,
                )
            )
        return response, status_code


def change_temporary_reservation(
    repository: SqlAlchemyOperationalRepository,
    principal: AuthenticatedPrincipal,
    conductor_id: UUID,
    change: CambioReservaTemporal,
    idempotency_key: str,
    *,
    ttl_seconds: int | None,
    now: datetime | None = None,
) -> tuple[ResultadoReservaTemporal, int]:
    if change.estado_temporal is EstadoTemporal.RESERVADO and ttl_seconds is None:
        raise DependencyUnavailableError(
            "El TTL de reservas no está configurado por acuerdo operativo."
        )

    current_time = now or datetime.now(timezone.utc)
    operation = f"reservation:{conductor_id}"
    request_hash = _hash_payload(
        {
            "conductor_id": str(conductor_id),
            **change.model_dump(mode="json"),
        }
    )

    with repository.transaction():
        repository.lock_conductor(conductor_id)
        previous_request = repository.get_idempotency_record(
            actor_id=principal.subject,
            operation=operation,
            key=idempotency_key,
        )
        if previous_request is not None:
            if previous_request.body_hash != request_hash:
                raise DomainError(
                    status_code=422,
                    code="IDEMPOTENCY_KEY_REUSED",
                    title="Solicitud no procesable",
                    detail="Idempotency-Key ya fue utilizada con otro cuerpo.",
                )
            return (
                ResultadoReservaTemporal.model_validate(
                    previous_request.response_body
                ),
                previous_request.response_status,
            )

        if change.estado_temporal is EstadoTemporal.RESERVADO:
            state = repository.get_state(conductor_id)
            if state is None:
                raise DomainError(
                    status_code=404,
                    code="CONDUCTOR_NOT_FOUND",
                    title="Conductor no encontrado",
                    detail="No existe una proyección operativa para el conductor.",
                )
            if not state.connected or not state.available:
                raise DomainError(
                    status_code=409,
                    code="DRIVER_NOT_ELIGIBLE",
                    title="Conductor no elegible",
                    detail="El conductor no está conectado y disponible.",
                )

        reservation = repository.get_reservation(conductor_id, for_update=True)
        is_active = (
            reservation is not None
            and reservation.estado_temporal == EstadoTemporal.RESERVADO.value
            and reservation.expira_en is not None
            and reservation.expira_en > current_time
        )

        if change.estado_temporal is EstadoTemporal.RESERVADO:
            if is_active and reservation.solicitud_id != change.solicitud_id:
                raise DomainError(
                    status_code=409,
                    code="DRIVER_ALREADY_RESERVED",
                    title="Conductor reservado",
                    detail="El conductor ya está reservado por otra solicitud.",
                )
            if is_active:
                status_code = 200
                response = ResultadoReservaTemporal(
                    conductor_id=conductor_id,
                    solicitud_id=change.solicitud_id,
                    estado_temporal=EstadoTemporal.RESERVADO,
                    actualizado_en=reservation.actualizado_en,
                    expira_en=reservation.expira_en,
                    idempotente=True,
                )
            else:
                expires_at = current_time + timedelta(seconds=ttl_seconds or 0)
                reservation = ReservaTemporalORM(
                    conductor_id=conductor_id,
                    solicitud_id=change.solicitud_id,
                    estado_temporal=EstadoTemporal.RESERVADO.value,
                    creada_en=current_time,
                    actualizado_en=current_time,
                    expira_en=expires_at,
                )
                repository.save_reservation(reservation)
                status_code = 201
                response = ResultadoReservaTemporal(
                    conductor_id=conductor_id,
                    solicitud_id=change.solicitud_id,
                    estado_temporal=EstadoTemporal.RESERVADO,
                    actualizado_en=current_time,
                    expira_en=expires_at,
                    idempotente=False,
                )
        else:
            if reservation is None:
                raise DomainError(
                    status_code=404,
                    code="RESERVATION_NOT_FOUND",
                    title="Reserva no encontrada",
                    detail="No existe una reserva para el conductor indicado.",
                )
            if reservation.solicitud_id != change.solicitud_id:
                raise DomainError(
                    status_code=409,
                    code="RESERVATION_OWNER_MISMATCH",
                    title="Conflicto de reserva",
                    detail="Solo la solicitud propietaria puede liberar la reserva.",
                )
            if reservation.estado_temporal != EstadoTemporal.LIBERADO.value:
                reservation.estado_temporal = EstadoTemporal.LIBERADO.value
                reservation.actualizado_en = current_time
                reservation.expira_en = None
                repository.save_reservation(reservation)
            response = ResultadoReservaTemporal(
                conductor_id=conductor_id,
                solicitud_id=change.solicitud_id,
                estado_temporal=EstadoTemporal.LIBERADO,
                actualizado_en=reservation.actualizado_en,
                expira_en=None,
                idempotente=not is_active,
            )
            status_code = 200

        repository.save_idempotency_record(
            RegistroIdempotenciaORM(
                id=uuid4(),
                actor_id=principal.subject,
                operacion=operation,
                idempotency_key=idempotency_key,
                body_hash=request_hash,
                response_status=status_code,
                response_body=response.model_dump(mode="json"),
                creado_en=current_time,
            )
        )
        return response, status_code
