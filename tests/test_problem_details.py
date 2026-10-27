import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.errors import (
    DependencyTimeoutError,
    DependencyUnavailableError,
    DomainError,
)
from app.core.middleware import REQUEST_ID_HEADER, RequestIdMiddleware
from app.core.problem_details import register_problem_details_handlers
from app.schemas.schemas import ProblemaDominio, ProblemaGenerico


@pytest.fixture
def client() -> TestClient:
    application = FastAPI()
    application.add_middleware(RequestIdMiddleware)
    register_problem_details_handlers(application)

    @application.get("/http-error")
    async def http_error() -> None:
        raise HTTPException(status_code=403, detail="forbidden")

    @application.get("/validation-error/{item_id}")
    async def validation_error(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    @application.get("/domain-error")
    async def domain_error() -> None:
        raise DomainError(
            status_code=409,
            code="DRIVER_RESERVED",
            title="Conductor no disponible para reserva",
            detail="El conductor ya está reservado por otra solicitud.",
        )

    @application.get("/unexpected-error")
    async def unexpected_error() -> None:
        raise RuntimeError("sensitive internal detail")

    @application.get("/dependency-unavailable")
    async def dependency_unavailable() -> None:
        raise DependencyUnavailableError()

    @application.get("/dependency-timeout")
    async def dependency_timeout() -> None:
        raise DependencyTimeoutError()

    return TestClient(application, raise_server_exceptions=False)


def assert_problem_response(
    response,
    *,
    expected_status: int,
    expected_code: str,
    expected_request_id: str,
) -> None:
    assert response.status_code == expected_status
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers[REQUEST_ID_HEADER] == expected_request_id
    body = response.json()
    schema_type = (
        ProblemaGenerico
        if body["type"] == "about:blank"
        else ProblemaDominio
    )
    validated_body = schema_type.model_validate(body)
    assert body["status"] == expected_status
    assert body["code"] == expected_code
    assert body["trace_id"] == expected_request_id
    assert body["detail"]
    assert "type" in body
    assert "title" in body
    assert "instance" in body
    assert validated_body.status == response.status_code


@pytest.mark.parametrize(
    ("path", "expected_status", "expected_code"),
    [
        ("/http-error", 403, "FORBIDDEN"),
        ("/validation-error/not-an-integer", 422, "VALIDATION_ERROR"),
        ("/domain-error", 409, "DRIVER_RESERVED"),
        ("/dependency-unavailable", 503, "DEPENDENCY_UNAVAILABLE"),
        ("/dependency-timeout", 504, "DEPENDENCY_TIMEOUT"),
        ("/unexpected-error", 500, "INTERNAL_ERROR"),
    ],
)
def test_problem_details_preserves_status_and_request_id(
    client: TestClient,
    path: str,
    expected_status: int,
    expected_code: str,
) -> None:
    request_id = "problem-details-test"
    response = client.get(path, headers={REQUEST_ID_HEADER: request_id})

    assert_problem_response(
        response,
        expected_status=expected_status,
        expected_code=expected_code,
        expected_request_id=request_id,
    )
    if expected_status == 500:
        assert "sensitive internal detail" not in response.text
