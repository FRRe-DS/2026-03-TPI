from fastapi import APIRouter, Depends, Request, Response

from app.core.auth import AuthenticatedPrincipal, get_authenticated_principal
from app.core.errors import DomainError
from app.repositories.dependencies import get_location_repository
from app.repositories.locations import LocationRepository
from app.schemas.schemas import ActualizarUbicacion, UbicacionRegistrada
from app.servicios.operaciones import register_location

router = APIRouter(prefix="/api/v1/ubicaciones", tags=["Ubicaciones"])


@router.post(
    "",
    response_model=UbicacionRegistrada,
    status_code=201,
    responses={200: {"model": UbicacionRegistrada, "description": "Ubicación actualizada."}},
)
async def registrar_ubicacion(
    location: ActualizarUbicacion,
    request: Request,
    response: Response,
    principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    repository: LocationRepository = Depends(get_location_repository),
) -> UbicacionRegistrada:
    if principal.subject != location.conductor_id:
        raise DomainError(
            status_code=403,
            code="FORBIDDEN",
            title="Sin permiso",
            detail="Solo se puede actualizar la ubicación del conductor autenticado.",
        )
    result, response.status_code = await register_location(
        repository,
        location,
        now=request.app.state.clock(),
    )
    return result
