from pathlib import Path
from typing import Any

import yaml
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import DomainError
from app.core.problem_details import _HTTP_PROBLEMS
from app.main import app

_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
_CONTRACT_PATH = Path(__file__).resolve().parents[1] / "openapi.yml"


def _resolve_schema(schema: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    reference = schema.get("$ref")
    while reference is not None:
        _, _, pointer = reference.partition("#/")
        current: Any = document
        for segment in pointer.split("/"):
            current = current[segment]
        schema = current
        reference = schema.get("$ref")
    return schema


def _assert_schema_contract(
    contract_schema: dict[str, Any],
    app_schema: dict[str, Any],
    contract: dict[str, Any],
    generated: dict[str, Any],
    *,
    path: str,
) -> None:
    contract_schema = _resolve_schema(contract_schema, contract)
    app_schema = _resolve_schema(app_schema, generated)

    if "anyOf" in contract_schema:
        options = [
            option
            for option in contract_schema["anyOf"]
            if option.get("type") != "null"
        ]
        assert len(options) == 1, path
        contract_schema = _resolve_schema(options[0], contract)

    if "anyOf" in app_schema:
        options = [
            option for option in app_schema["anyOf"] if option.get("type") != "null"
        ]
        assert len(options) == 1, path
        app_schema = _resolve_schema(options[0], generated)

    contract_properties = contract_schema.get("properties", {})
    app_properties = app_schema.get("properties", {})
    if contract_properties or app_properties:
        contract_required = set(contract_schema.get("required", []))
        app_required = set(app_schema.get("required", []))
        assert contract_required == app_required, path
        assert set(contract_properties) == set(app_properties), path
        if contract_schema.get("additionalProperties") is False:
            assert app_schema.get("additionalProperties") is False, path
        for name in contract_properties:
            _assert_schema_contract(
                contract_properties[name],
                app_properties[name],
                contract,
                generated,
                path=f"{path}.{name}",
            )
        return

    if contract_schema.get("type") == "array":
        assert app_schema.get("type") == "array", path
        _assert_schema_contract(
            contract_schema["items"],
            app_schema["items"],
            contract,
            generated,
            path=f"{path}[]",
        )
        return

    if contract_schema.get("type") is not None:
        assert contract_schema["type"] == app_schema.get("type"), path
    if contract_schema.get("enum") is not None:
        assert set(contract_schema["enum"]) == set(app_schema.get("enum", [])), path


def test_app_routes_methods_status_codes_and_json_match_openapi_contract() -> None:
    contract = yaml.safe_load(_CONTRACT_PATH.read_text(encoding="utf-8"))
    generated = app.openapi()
    contract_paths = contract["paths"]
    generated_paths = generated["paths"]
    implementation_only_paths = {"/", "/PruebaM4/Piloto"}

    assert set(generated_paths) == set(contract_paths) | implementation_only_paths

    for path, contract_path_item in contract_paths.items():
        generated_path_item = generated_paths[path]
        contract_methods = {
            method
            for method in contract_path_item
            if method in _HTTP_METHODS
        }
        generated_methods = {
            method for method in generated_path_item if method in _HTTP_METHODS
        }
        assert contract_methods == generated_methods, path

        for method in contract_methods:
            contract_operation = contract_path_item[method]
            generated_operation = generated_path_item[method]
            contract_responses = contract_operation["responses"]
            generated_responses = generated_operation["responses"]
            successful_contract_statuses = {
                status for status in contract_responses if status.startswith("2")
            }
            successful_generated_statuses = {
                status for status in generated_responses if status.startswith("2")
            }
            assert successful_contract_statuses == successful_generated_statuses, (
                path,
                method,
            )
            contract_error_statuses = {
                status for status in contract_responses if status.startswith(("4", "5"))
            }
            supported_problem_statuses = {str(status) for status in _HTTP_PROBLEMS}
            assert contract_error_statuses <= supported_problem_statuses, (path, method)
            assert set(contract_responses) == (
                set(generated_responses) | contract_error_statuses
            ), (path, method)

            contract_request_body = contract_operation.get("requestBody")
            generated_request_body = generated_operation.get("requestBody")
            assert (contract_request_body is None) == (generated_request_body is None), (
                path,
                method,
            )
            if contract_request_body is not None:
                contract_body_content = contract_request_body["content"]
                generated_body_content = generated_request_body["content"]
                assert set(contract_body_content) == set(generated_body_content), (
                    path,
                    method,
                )
                for media_type, contract_body in contract_body_content.items():
                    _assert_schema_contract(
                        contract_body["schema"],
                        generated_body_content[media_type]["schema"],
                        contract,
                        generated,
                        path=f"{method.upper()} {path} request",
                    )

            for status in successful_contract_statuses:
                contract_content = contract_responses[status].get("content", {})
                generated_content = generated_responses[status].get("content", {})
                if not contract_content:
                    assert not generated_content, (path, method, status)
                    continue
                assert set(contract_content) == set(generated_content), (
                    path,
                    method,
                    status,
                )
                for media_type, contract_body in contract_content.items():
                    _assert_schema_contract(
                        contract_body["schema"],
                        generated_content[media_type]["schema"],
                        contract,
                        generated,
                        path=f"{method.upper()} {path} {status}",
                    )

            for status in contract_error_statuses:
                error_content = contract_responses[status].get("content", {})
                if error_content:
                    assert "application/problem+json" in error_content, (
                        path,
                        method,
                        status,
                    )

    assert DomainError in app.exception_handlers
    assert RequestValidationError in app.exception_handlers
    assert StarletteHTTPException in app.exception_handlers
