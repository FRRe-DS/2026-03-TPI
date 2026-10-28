import asyncio
from collections.abc import Callable
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.clients.m3 import (
    ClienteM3,
    ElegibilidadConductor,
    EstadoHabilitacionM3,
    RespuestaElegibilidadM3,
)
from app.core.config import Settings
from app.core.errors import M3TimeoutError, M3UnavailableError
from app.core.observability import request_id_context
from app.main import create_app
from app.repositories.m3_dependencies import get_m3_client
from app.schemas.schemas import TipoVehiculo

CONDUCTOR_ID = UUID("018f1f20-7b4a-7cc2-9d41-66382a18cc5a")
ELIGIBILITY_PAYLOAD = {
    "estado_habilitacion": "APPROVED",
    "tipos_vehiculo_habilitados": ["AUTO", "MOTO"],
}


def _client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> ClienteM3:
    return ClienteM3(
        base_url="https://m3.example.test",
        service_token="service-token",
        eligibility_path="/configured/drivers/{conductor_id}/eligibility",
        timeout_seconds=0.25,
        transport=httpx.MockTransport(handler),
    )


def test_m3_client_sends_service_auth_request_id_and_maps_approved_eligibility() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=ELIGIBILITY_PAYLOAD)

    async def scenario() -> ElegibilidadConductor:
        client = _client(handler)
        token = request_id_context.set("m3-correlated-request-1")
        try:
            return await client.get_eligibility(CONDUCTOR_ID)
        finally:
            request_id_context.reset(token)
            await client.aclose()

    result = asyncio.run(scenario())

    assert result.estado_habilitacion is EstadoHabilitacionM3.APPROVED
    assert result.aprobado is True
    assert result.habilitado_para(TipoVehiculo.AUTO) is True
    assert result.habilitado_para(TipoVehiculo.MOTO) is True
    assert result.habilitado_para(None) is True
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert str(CONDUCTOR_ID) in str(requests[0].url)
    assert requests[0].headers["Authorization"] == "Bearer service-token"
    assert requests[0].headers["X-Request-Id"] == "m3-correlated-request-1"


def test_m3_client_configures_finite_http_timeouts() -> None:
    client = _client(lambda _request: httpx.Response(200, json=ELIGIBILITY_PAYLOAD))
    timeout = client._client.timeout

    assert timeout.connect == 0.25
    assert timeout.read == 0.25
    assert timeout.write == 0.25
    assert timeout.pool == 0.25

    asyncio.run(client.aclose())


@pytest.mark.parametrize(
    ("status", "expected_error"),
    [
        (404, M3UnavailableError),
        (401, M3UnavailableError),
        (503, M3UnavailableError),
        (504, M3TimeoutError),
    ],
)
def test_m3_client_fails_closed_on_http_errors(
    status: int, expected_error: type[Exception]
) -> None:
    client = _client(lambda _request: httpx.Response(status))

    async def scenario() -> None:
        try:
            with pytest.raises(expected_error):
                await client.get_eligibility(CONDUCTOR_ID)
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_m3_client_maps_transport_timeout_to_explicit_timeout_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sensitive transport detail")

    client = _client(handler)

    async def scenario() -> None:
        try:
            with pytest.raises(M3TimeoutError) as error:
                await client.get_eligibility(CONDUCTOR_ID)
            assert "sensitive transport detail" not in str(error.value)
            assert error.value.status_code == 504
        finally:
            await client.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "payload",
    [
        {"estado_habilitacion": "APPROVED"},
        {"tipos_vehiculo_habilitados": ["AUTO"]},
        {
            "estado_habilitacion": "UNKNOWN",
            "tipos_vehiculo_habilitados": ["AUTO"],
        },
        {
            "estado_habilitacion": "APPROVED",
            "tipos_vehiculo_habilitados": ["TRUCK"],
        },
        {
            "estado_habilitacion": "APPROVED",
            "tipos_vehiculo_habilitados": ["AUTO", "AUTO"],
        },
        {
            **ELIGIBILITY_PAYLOAD,
            "conductor_id": str(CONDUCTOR_ID),
        },
    ],
)
def test_m3_client_rejects_incomplete_or_uncontracted_responses(
    payload: dict[str, object],
) -> None:
    client = _client(lambda _request: httpx.Response(200, json=payload))

    async def scenario() -> None:
        try:
            with pytest.raises(M3UnavailableError) as error:
                await client.get_eligibility(CONDUCTOR_ID)
            assert error.value.status_code == 503
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_m3_client_rejects_malformed_json_response() -> None:
    client = _client(
        lambda _request: httpx.Response(200, content=b"{not-json")
    )

    async def scenario() -> None:
        try:
            with pytest.raises(M3UnavailableError):
                await client.get_eligibility(CONDUCTOR_ID)
        finally:
            await client.aclose()

    asyncio.run(scenario())


def test_m3_empty_eligible_vehicle_list_is_valid_but_not_eligible() -> None:
    parsed = RespuestaElegibilidadM3.model_validate(
        {
            "estado_habilitacion": "APPROVED",
            "tipos_vehiculo_habilitados": [],
        }
    )
    eligibility = ElegibilidadConductor.from_response(parsed)

    assert eligibility.aprobado is True
    assert eligibility.habilitado_para(None) is False
    assert eligibility.habilitado_para(TipoVehiculo.AUTO) is False


@pytest.mark.parametrize(
    "status",
    ["PENDING", "OBSERVED", "SUSPENDED", "REJECTED"],
)
def test_non_approved_status_is_not_eligible(status: str) -> None:
    parsed = RespuestaElegibilidadM3.model_validate(
        {
            "estado_habilitacion": status,
            "tipos_vehiculo_habilitados": ["AUTO"],
        }
    )
    eligibility = ElegibilidadConductor.from_response(parsed)

    assert eligibility.aprobado is False
    assert eligibility.habilitado_para(TipoVehiculo.AUTO) is False


def test_unsupported_vehicle_is_not_eligible() -> None:
    approved = ElegibilidadConductor.from_response(
        RespuestaElegibilidadM3.model_validate(
            {
                "estado_habilitacion": "APPROVED",
                "tipos_vehiculo_habilitados": ["MOTO"],
            }
        )
    )
    assert approved.habilitado_para(TipoVehiculo.AUTO) is False


def test_m3_client_closes_in_fastapi_lifespan(monkeypatch: pytest.MonkeyPatch) -> None:
    closed: list[bool] = []

    class ClientStub:
        def __init__(self, **_kwargs: object) -> None:
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True
            closed.append(self.closed)

    monkeypatch.setattr("app.main.ClienteM3", ClientStub)
    app = create_app(
        Settings(
            _env_file=None,
            redis_url=None,
            m3_base_url="https://m3.example.test",
            m3_service_token="service-token",
            m3_eligibility_path="/configured/drivers/{conductor_id}/eligibility",
        )
    )

    with TestClient(app):
        assert app.state.m3_client is not None
        assert closed == []

    assert closed == [True]


def test_missing_m3_configuration_is_an_explicit_dependency_error() -> None:
    app = create_app(Settings(_env_file=None, redis_url=None))

    async def scenario() -> None:
        from starlette.requests import Request

        with pytest.raises(M3UnavailableError):
            get_m3_client(Request({"type": "http", "app": app, "headers": []}))

    asyncio.run(scenario())


def test_m3_configuration_requires_the_complete_contract() -> None:
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            m3_base_url="https://m3.example.test",
        )

    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            m3_base_url="https://m3.example.test",
            m3_service_token="service-token",
            m3_eligibility_path="/drivers/{driver_id}",
        )
