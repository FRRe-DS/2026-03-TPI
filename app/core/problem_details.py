import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import DomainError
from app.schemas.schemas import ProblemaDominio, ProblemaGenerico

logger = logging.getLogger(__name__)

_HTTP_PROBLEMS: dict[int, tuple[str, str, str]] = {
    400: ("BAD_REQUEST", "Solicitud inválida", "La solicitud no es válida."),
    401: ("UNAUTHORIZED", "No autenticado", "Se requiere autenticación válida."),
    403: ("FORBIDDEN", "Sin permiso", "No está autorizado para esta operación."),
    404: ("NOT_FOUND", "Recurso no encontrado", "El recurso solicitado no existe."),
    405: ("METHOD_NOT_ALLOWED", "Método no permitido", "El método HTTP no está permitido."),
    409: ("CONFLICT", "Conflicto", "La solicitud entra en conflicto con el estado actual."),
    422: ("UNPROCESSABLE_REQUEST", "Solicitud no procesable", "La solicitud no puede procesarse."),
    429: ("RATE_LIMIT_EXCEEDED", "Límite excedido", "Se excedió el límite de solicitudes."),
    500: ("INTERNAL_ERROR", "Error interno", "Ocurrió un error interno."),
    503: ("SERVICE_UNAVAILABLE", "Servicio no disponible", "El servicio no está disponible temporalmente."),
    504: ("GATEWAY_TIMEOUT", "Tiempo de espera agotado", "Una dependencia no respondió a tiempo."),
}


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _problem_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str,
    problem_type: str = "about:blank",
    invalid_params: list[dict[str, str]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    body_data: dict[str, Any] = {
        "type": problem_type,
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": request.url.path,
        "code": code,
        "trace_id": request_id,
    }
    if invalid_params is not None:
        body_data["invalid_params"] = invalid_params

    response_headers = dict(headers or {})
    if request_id:
        response_headers["X-Request-Id"] = request_id

    problem_schema = (
        ProblemaDominio if problem_type != "about:blank" else ProblemaGenerico
    )
    try:
        body = problem_schema.model_validate(body_data).model_dump(
            mode="json", exclude_none=True
        )
    except ValidationError:
        logger.exception(
            "Problem Details response failed schema validation",
            extra={"request_id": request_id, "code": code},
        )
        status_code = 500
        body = ProblemaGenerico(
            type="about:blank",
            title="Error interno",
            status=status_code,
            detail="Ocurrió un error interno.",
            instance=request.url.path,
            code="INTERNAL_ERROR",
            trace_id=request_id,
        ).model_dump(mode="json", exclude_none=True)
        response_headers = {"X-Request-Id": request_id} if request_id else {}

    return JSONResponse(
        status_code=status_code,
        content=body,
        headers=response_headers,
        media_type="application/problem+json",
    )


async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    return _problem_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        title=exc.title,
        detail=exc.detail,
        problem_type=exc.problem_type,
    )


async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    invalid_params = [
        {
            "name": ".".join(str(part) for part in error["loc"]),
            "reason": error["msg"],
        }
        for error in exc.errors()
    ]
    return _problem_response(
        request,
        status_code=422,
        code="VALIDATION_ERROR",
        title="Solicitud no procesable",
        detail="Uno o más campos de la solicitud no son válidos.",
        invalid_params=invalid_params,
    )


async def handle_http_error(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code, title, safe_detail = _HTTP_PROBLEMS.get(
        exc.status_code,
        ("HTTP_ERROR", "Error de solicitud", "No fue posible procesar la solicitud."),
    )
    return _problem_response(
        request,
        status_code=exc.status_code,
        code=code,
        title=title,
        detail=safe_detail,
        headers=exc.headers,
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled application exception",
        exc_info=(type(exc), exc, exc.__traceback__),
        extra={"request_id": _request_id(request)},
    )
    return _problem_response(
        request,
        status_code=500,
        code="INTERNAL_ERROR",
        title="Error interno",
        detail="Ocurrió un error interno.",
    )


def register_problem_details_handlers(application: FastAPI) -> None:
    application.add_exception_handler(DomainError, handle_domain_error)
    application.add_exception_handler(RequestValidationError, handle_validation_error)
    application.add_exception_handler(StarletteHTTPException, handle_http_error)
    application.add_exception_handler(Exception, handle_unexpected_error)
