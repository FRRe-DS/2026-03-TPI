import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import REQUEST_ID_HEADER, RequestIdMiddleware
from app.core.observability import (
    RedactingLogFilter,
    StructuredJsonFormatter,
    sanitize_text,
)


def test_sanitize_text_redacts_credentials_query_values_and_gps() -> None:
    message = (
        "url=https://maps.example/route?access_token=query-secret&mode=driving "
        "Authorization: Bearer header-secret password=plain-secret "
        "latitud=-27.451234 longitud=-58.986543"
    )

    sanitized = sanitize_text(message)

    assert "query-secret" not in sanitized
    assert "header-secret" not in sanitized
    assert "plain-secret" not in sanitized
    assert "-27.451234" not in sanitized
    assert "-58.986543" not in sanitized
    assert "mode=driving" in sanitized


def test_sanitize_text_redacts_runtime_bearer_value() -> None:
    credential = "runtime" + "-credential"
    message = "Authorization: " + "Bear" + "er " + credential

    sanitized = sanitize_text(message)

    assert credential not in sanitized
    assert "[REDACTED]" in sanitized


def test_sanitize_text_redacts_credentials_embedded_in_url() -> None:
    credential = "url" + "-credential"
    message = "https://service-user:" + credential + "@maps.example/path"

    sanitized = sanitize_text(message)

    assert credential not in sanitized
    assert "[REDACTED]@" in sanitized


def test_redacting_filter_sanitizes_structured_fields_and_adds_correlation() -> None:
    log_filter = RedactingLogFilter()
    record = logging.LogRecord(
        "app.test",
        logging.INFO,
        __file__,
        1,
        "Request failed for token=%s",
        ("message-secret",),
        None,
    )
    record.authorization = "Bearer extra-secret"
    record.latitude = -27.451234

    assert log_filter.filter(record)

    assert "message-secret" not in record.getMessage()
    assert record.authorization == "[REDACTED]"
    assert record.latitude == "[REDACTED]"


def test_request_logs_are_structured_redacted_and_correlated(
    caplog,
) -> None:
    application = FastAPI()
    application.add_middleware(RequestIdMiddleware)
    test_logger = logging.getLogger("app.test_observability")

    @application.get("/log-sensitive")
    async def log_sensitive() -> dict[str, str]:
        test_logger.warning(
            "Map request url=%s Authorization: Bearer %s "
            "latitud=%s longitud=%s",
            (
                "https://maps.example/route?"
                "api_key=query-secret&profile=car"
            ),
            "header-secret",
            "-27.451234",
            "-58.986543",
            extra={
                "password": "field-secret",
                "latitude": -27.451234,
                "longitude": -58.986543,
            },
        )
        return {"ok": "true"}

    request_id = "observability-request-123"
    with caplog.at_level(logging.WARNING):
        response = TestClient(application).get(
            "/log-sensitive", headers={REQUEST_ID_HEADER: request_id}
        )

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == request_id
    log_record = next(
        record
        for record in caplog.records
        if record.name == "app.test_observability"
    )
    assert log_record.request_id == request_id
    assert log_record.password == "[REDACTED]"
    assert log_record.latitude == "[REDACTED]"
    assert log_record.longitude == "[REDACTED]"

    output = caplog.text
    for sensitive_value in (
        "query-secret",
        "header-secret",
        "field-secret",
        "-27.451234",
        "-58.986543",
    ):
        assert sensitive_value not in output
    assert request_id in output
    assert "profile=car" in output
    json_log = next(
        line
        for line in output.splitlines()
        if '"logger":"app.test_observability"' in line
    )
    assert json.loads(json_log)["request_id"] == request_id


def test_structured_formatter_emits_json_with_request_id() -> None:
    record = logging.LogRecord(
        "app.test",
        logging.INFO,
        __file__,
        1,
        "Request completed",
        (),
        None,
    )
    record.request_id = "json-request-id"

    payload = json.loads(StructuredJsonFormatter().format(record))

    assert payload["message"] == "Request completed"
    assert payload["request_id"] == "json-request-id"
    assert payload["level"] == "INFO"
