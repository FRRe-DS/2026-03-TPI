from fastapi import APIRouter, Depends

from app.clients.geocoding import NominatimGeocodingAdapter
from app.core.auth import AuthenticatedPrincipal, get_authenticated_principal
from app.schemas.schemas import ConsultaGeocodificacion, ResultadoGeocodificacion
from app.servicios.geocoding import get_geocoding_adapter

router = APIRouter(prefix="/api/v1/geocodificaciones", tags=["Geocodificación"])


@router.post("", response_model=ResultadoGeocodificacion)
async def geocodificar_direccion(
    query: ConsultaGeocodificacion,
    _principal: AuthenticatedPrincipal = Depends(get_authenticated_principal),
    adapter: NominatimGeocodingAdapter = Depends(get_geocoding_adapter),
) -> ResultadoGeocodificacion:
    return await adapter.geocode(query)
