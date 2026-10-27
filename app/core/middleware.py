import re
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.datastructures import MutableHeaders

from app.core.observability import configure_logging, request_id_context

ASGIApp = Callable[
    [dict[str, Any], Callable[..., Awaitable[None]], Callable[..., Awaitable[None]]],
    Awaitable[None],
]

REQUEST_ID_HEADER = "X-Request-Id"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        configure_logging()
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[..., Awaitable[None]],
        send: Callable[..., Awaitable[None]],
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = self._get_request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id
        context_token = request_id_context.set(request_id)

        async def send_with_request_id(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            request_id_context.reset(context_token)

    @staticmethod
    def _get_request_id(scope: dict[str, Any]) -> str:
        headers = scope.get("headers", [])
        supplied_id = next(
            (
                value.decode("latin-1")
                for name, value in headers
                if name.lower() == REQUEST_ID_HEADER.lower().encode("ascii")
            ),
            "",
        )
        if REQUEST_ID_PATTERN.fullmatch(supplied_id):
            return supplied_id
        return str(uuid.uuid4())
