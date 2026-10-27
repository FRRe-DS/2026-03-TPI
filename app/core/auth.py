from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import DependencyUnavailableError


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    subject: UUID


class TokenAuthenticator(Protocol):
    def __call__(
        self, token: str, request: Request
    ) -> Awaitable[AuthenticatedPrincipal]: ...


_bearer_scheme = HTTPBearer(auto_error=False)


async def get_authenticated_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthenticatedPrincipal:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Se requiere autenticación.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    authenticator: TokenAuthenticator | None = getattr(
        request.app.state, "token_authenticator", None
    )
    if authenticator is None:
        raise DependencyUnavailableError(
            "La validación de identidad de M1 no está configurada."
        )
    return await authenticator(credentials.credentials, request)
