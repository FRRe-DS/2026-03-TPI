from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response

from app.core.auth import AuthenticatedPrincipal, get_authenticated_principal
from app.repositories.dependencies import get_operational_repository
from app.repositories.operational import SqlAlchemyOperationalRepository
from app.schemas.schemas import CambioReservaTemporal, ResultadoReservaTemporal
from app.servicios.operaciones import change_temporary_reservation

router = APIRouter(
    prefix="/api/v1/conductores/{conductor_id}/reserva",
    tags=["Disponibilidad"],
)


@router.post(
    "",
    response_model=ResultadoReservaTemporal,
    status_code=201,
    responses={
        200: {
            "model": ResultadoReservaTemporal,
            "description": "Reserva existente del mismo titular o liberación.",
        }
    },
)
def cambiar_reserva_temporal(
    conductor_id: UUID,
    change: CambioReservaTemporal,
    request: Request,
    response: Response,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=255)
    ],
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    repository: SqlAlchemyOperationalRepository = Depends(
        get_operational_repository
    ),
) -> ResultadoReservaTemporal:
    result, response.status_code = change_temporary_reservation(
        repository,
        principal,
        conductor_id,
        change,
        idempotency_key,
        ttl_seconds=request.app.state.settings.reservation_ttl_seconds,
        now=request.app.state.clock(),
    )
    return result
