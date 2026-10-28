from fastapi import Request

from app.clients.m3 import ClienteM3
from app.core.errors import M3UnavailableError


def get_m3_client(request: Request) -> ClienteM3:
    client = getattr(request.app.state, "m3_client", None)
    if client is None:
        raise M3UnavailableError()
    return client
