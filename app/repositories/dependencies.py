from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import DependencyUnavailableError
from app.database import get_db
from app.repositories.locations import LocationRepository
from app.repositories.operational import SqlAlchemyOperationalRepository


def get_location_repository(request: Request) -> LocationRepository:
    repository = getattr(request.app.state, "location_repository", None)
    if repository is None:
        raise DependencyUnavailableError(
            "El repositorio de ubicación no está configurado."
        )
    return repository


def get_operational_repository(
    session: Session = Depends(get_db),
) -> SqlAlchemyOperationalRepository:
    return SqlAlchemyOperationalRepository(session)
