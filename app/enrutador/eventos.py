from fastapi import APIRouter

from app.core.errors import DomainError
from app.schemas.schemas import EventoPruebaEntrada, EventoPruebaSalida
from app.servicios.procesadorDeEventos import procesarEventoPrueba

prueba = APIRouter(tags=["PruebaPilotoM4"])


@prueba.post("/Piloto", response_model=EventoPruebaSalida)
async def recibir_evento(evento: EventoPruebaEntrada) -> dict:
    try:
        return await procesarEventoPrueba(evento.model_dump())
    except ValueError as error:
        raise DomainError(
            status_code=400,
            code="LOCATION_OUTSIDE_COVERAGE",
            title="Solicitud inválida",
            detail=str(error),
        ) from error
