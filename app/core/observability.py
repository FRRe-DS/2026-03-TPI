import json
import logging
import re
from collections.abc import Mapping
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)

_SENSITIVE_VALUE = "[REDACTED]"
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|token|access[_-]?token|refresh[_-]?token|"
    r"api[_-]?key|client[_-]?secret|private[_-]?key|secret[_-]?key|secret|"
    r"authorization|credential|idempotency[_-]?key)"
    r"(\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;&]+)"
)
_SENSITIVE_QUERY = re.compile(
    r"(?i)([?&](?:password|passwd|token|access[_-]?token|refresh[_-]?token|"
    r"api[_-]?key|client[_-]?secret|private[_-]?key|secret[_-]?key|secret|"
    r"authorization|credential|idempotency[_-]?key|"
    r"(?:origen|destino)[_-](?:latitud|longitud))=)"
    r"[^&#\s]+"
)
_BEARER_TOKEN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*")
_URL_CREDENTIALS = re.compile(r"(?i)(://)[^/@\s:]+:[^/@\s]+@")
_ABSOLUTE_URL = re.compile(r"(?i)\bhttps?://[^\s\"'<>]+")
_COORDINATE_ASSIGNMENT = re.compile(
    r"(?i)\b((?:[a-z][a-z0-9]*[_-])*(?:(?:origen|destino)[_-])?"
    r"(?:lat(?:itude|itud)?|lon(?:gitude|gitud)?|lng))"
    r"(\s*[:=]\s*)-?\d{1,3}(?:\.\d+)?"
)
_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "client_secret",
    "private_key",
    "secret_key",
    "secret",
    "authorization",
    "credential",
    "idempotency_key",
    "lat",
    "latitude",
    "latitud",
    "lon",
    "lng",
    "longitude",
    "longitud",
    "gps",
    "coordinates",
    "coordenadas",
}
_STANDARD_RECORD_KEYS = set(logging.makeLogRecord({}).__dict__)


def sanitize_text(value: str) -> str:
    value = _ABSOLUTE_URL.sub("[URL REDACTED]", value)
    value = _URL_CREDENTIALS.sub(r"\1[REDACTED]@", value)
    value = _SENSITIVE_QUERY.sub(r"\1" + _SENSITIVE_VALUE, value)
    value = _BEARER_TOKEN.sub("Bearer " + _SENSITIVE_VALUE, value)
    value = _SECRET_ASSIGNMENT.sub(
        lambda match: match.group(1) + match.group(2) + _SENSITIVE_VALUE,
        value,
    )
    return _COORDINATE_ASSIGNMENT.sub(
        lambda match: match.group(1) + match.group(2) + _SENSITIVE_VALUE,
        value,
    )


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, Mapping):
        return {
            str(key): (
                _SENSITIVE_VALUE
                if str(key).lower().replace("-", "_") in _SENSITIVE_KEYS
                else _sanitize_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_value(item) for item in value]
    return value


class RedactingLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _sanitize_value(record.getMessage())
        record.args = ()
        record.request_id = (
            getattr(record, "request_id", None) or request_id_context.get()
        )

        for key, value in tuple(record.__dict__.items()):
            if key in _STANDARD_RECORD_KEYS or key == "request_id":
                continue
            normalized_key = key.lower().replace("-", "_")
            record.__dict__[key] = (
                _SENSITIVE_VALUE
                if normalized_key in _SENSITIVE_KEYS
                else _sanitize_value(value)
            )

        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_text(record.getMessage()),
        }
        request_id = (
            getattr(record, "request_id", None) or request_id_context.get()
        )
        if request_id:
            payload["request_id"] = request_id
        code = getattr(record, "code", None)
        if code:
            payload["code"] = code
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> None:
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        root_logger.addHandler(logging.StreamHandler())
        root_logger.setLevel(logging.INFO)

    formatter = StructuredJsonFormatter()
    log_filter = RedactingLogFilter()
    access_logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, RedactingLogFilter) for item in access_logger.filters):
        access_logger.addFilter(log_filter)

    for handler in root_logger.handlers + access_logger.handlers:
        if not any(isinstance(item, RedactingLogFilter) for item in handler.filters):
            handler.addFilter(log_filter)
        handler.setFormatter(formatter)
