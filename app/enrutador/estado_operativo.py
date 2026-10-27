from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.core.auth import AuthenticatedPrincipal, get_authenticated_principal
from app.repositories.dependencies import get_operational_repository
from app.repositories.operational import SqlAlchemyOperationalRepository
from app.schemas.schemas import EstadoOperativo, EstadoOperativoRegistrado
from app.servicios.operaciones import register_operational_state

router = APIRouter(
    prefix="/api/v1/conductores/{conductor_id}/estado-operativo",
    tags=["Disponibilidad"],
)


@router.post("", response_model=EstadoOperativoRegistrado, status_code=201)
def registrar_estado_operativo(
    conductor_id: UUID,
    event: EstadoOperativo,
    request: Request,
    response: Response,
    _principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    repository: SqlAlchemyOperationalRepository = Depends(
        get_operational_repository
    ),
) -> EstadoOperativoRegistrado:
    result, response.status_code = register_operational_state(
        repository,
        conductor_id,
        event,
        now=request.app.state.clock(),
    )
    return result
