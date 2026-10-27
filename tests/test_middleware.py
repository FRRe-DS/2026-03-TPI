import re

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
from app.core.problem_details import register_problem_details_handlers
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_request_id_is_preserved_when_valid(client: TestClient) -> None:
    request_id = "request_2026-10.27"

    response = client.get("/", headers={REQUEST_ID_HEADER: request_id})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == request_id


def test_request_id_is_generated_when_missing(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert re.fullmatch(
        r"[A-Za-z0-9._-]{1,128}", response.headers[REQUEST_ID_HEADER]
    )


@pytest.mark.parametrize("request_id", ["invalid id", "x" * 129])
def test_invalid_request_id_is_replaced(
    client: TestClient, request_id: str
) -> None:
    response = client.get("/", headers={REQUEST_ID_HEADER: request_id})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] != request_id
    assert re.fullmatch(
        r"[A-Za-z0-9._-]{1,128}", response.headers[REQUEST_ID_HEADER]
    )


def test_request_id_is_returned_on_handled_error(client: TestClient) -> None:
    request_id = "trace-validation-error"
    payload = {
        "evento_id": "123e4567-e89b-12d3-a456-426614174000",
        "lat": -34.6037,
        "lon": -58.3816,
        "ubicacion_texto": "Fuera de cobertura",
    }

    response = client.post(
        "/PruebaM4/Piloto",
        json=payload,
        headers={REQUEST_ID_HEADER: request_id},
    )

    assert response.status_code == 400
    assert response.headers[REQUEST_ID_HEADER] == request_id


def test_unhandled_error_returns_problem_details_with_request_id() -> None:
    test_app = FastAPI()
    test_app.add_middleware(RequestIdMiddleware)
    register_problem_details_handlers(test_app)
    register_problem_details_handlers(test_app)

    @test_app.get("/failure")
    async def fail() -> None:
        raise RuntimeError("sensitive internal detail")

    with TestClient(test_app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/failure")

    assert response.status_code == 500
    assert response.headers[REQUEST_ID_HEADER]
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["status"] == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert response.json()["instance"] == "/failure"
    assert "sensitive internal detail" not in response.text


def test_request_id_is_returned_on_http_error() -> None:
    test_app = FastAPI()
    test_app.add_middleware(RequestIdMiddleware)
    register_problem_details_handlers(test_app)
    register_problem_details_handlers(test_app)

    @test_app.get("/not-allowed")
    async def not_allowed() -> None:
        raise HTTPException(status_code=403, detail="forbidden")

    with TestClient(test_app) as test_client:
        response = test_client.get("/not-allowed")

    assert response.status_code == 403
    assert response.headers[REQUEST_ID_HEADER]
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "FORBIDDEN"


def test_validation_error_uses_problem_details_and_request_id() -> None:
    test_app = FastAPI()
    test_app.add_middleware(RequestIdMiddleware)
    register_problem_details_handlers(test_app)
    register_problem_details_handlers(test_app)

    @test_app.get("/items/{item_id}")
    async def read_item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    request_id = "invalid-item-id"
    with TestClient(test_app) as test_client:
        response = test_client.get(
            "/items/not-an-integer",
            headers={REQUEST_ID_HEADER: request_id},
        )

    assert response.status_code == 422
    assert response.headers[REQUEST_ID_HEADER] == request_id
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["status"] == 422
    assert response.json()["invalid_params"][0]["name"] == "path.item_id"


def test_domain_error_uses_stable_code_and_correlation_id() -> None:
    test_app = FastAPI()
    test_app.add_middleware(RequestIdMiddleware)
    register_problem_details_handlers(test_app)
    register_problem_details_handlers(test_app)

    @test_app.get("/domain-error")
    async def domain_error() -> None:
        raise DomainError(
            status_code=409,
            code="DRIVER_RESERVED",
            title="Conductor no disponible para reserva",
            detail="El conductor ya está reservado por otra solicitud.",
        )

    request_id = "reservation-conflict"
    with TestClient(test_app) as test_client:
        response = test_client.get(
            "/domain-error",
            headers={REQUEST_ID_HEADER: request_id},
        )

    assert response.status_code == 409
    assert response.headers[REQUEST_ID_HEADER] == request_id
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "DRIVER_RESERVED"
    assert response.json()["status"] == 409
    assert response.json()["trace_id"] == request_id


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (DependencyUnavailableError(), 503, "DEPENDENCY_UNAVAILABLE"),
        (DependencyTimeoutError(), 504, "DEPENDENCY_TIMEOUT"),
    ],
)
def test_dependency_error_uses_problem_details(
    error: DomainError, expected_status: int, expected_code: str
) -> None:
    test_app = FastAPI()
    test_app.add_middleware(RequestIdMiddleware)
    register_problem_details_handlers(test_app)
    register_problem_details_handlers(test_app)

    @test_app.get("/dependency-error")
    async def dependency_error() -> None:
        raise error

    with TestClient(test_app) as test_client:
        response = test_client.get("/dependency-error")

    assert response.status_code == expected_status
    assert response.headers[REQUEST_ID_HEADER]
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == expected_code
    assert response.json()["status"] == expected_status
