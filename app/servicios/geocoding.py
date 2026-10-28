from fastapi import Request

from app.clients.geocoding import NominatimGeocodingAdapter
from app.core.errors import DependencyUnavailableError


def get_geocoding_adapter(request: Request) -> NominatimGeocodingAdapter:
    adapter = getattr(request.app.state, "geocoding_adapter", None)
    if adapter is None:
        raise DependencyUnavailableError(
            "El proveedor de geocodificación no está configurado."
        )
    return adapter
