"""Dependency-free validation for the six frozen Event Copilot JSON Schemas.

This is intentionally a small JSON Schema 2020-12 subset. It implements only
the keywords used by ``specs/03-data/schemas`` so the hackathon demo can
validate every product boundary without adding a package installation step.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_ROOT = ROOT / "specs" / "03-data" / "schemas"


class SchemaValidationError(ValueError):
    """Raised when a value does not satisfy one of the frozen schemas."""


def validate_schema(instance: Any, schema_name: str) -> None:
    """Validate ``instance`` against a schema file and raise on the first error."""

    filename = schema_name if schema_name.endswith(".schema.json") else f"{schema_name}.schema.json"
    schema_path = SCHEMA_ROOT / filename
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    _validate(instance, schema, schema, schema_path, "$")


def _validate(
    instance: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    schema_path: Path,
    path: str,
) -> None:
    if "$ref" in schema:
        ref_schema, ref_root, ref_path = _resolve_ref(schema["$ref"], root_schema, schema_path)
        _validate(instance, ref_schema, ref_root, ref_path, path)
        return

    if "const" in schema and instance != schema["const"]:
        _fail(path, f"must equal {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        _fail(path, f"must be one of {schema['enum']!r}")

    expected = schema.get("type")
    if expected is not None and not _matches_type(instance, expected):
        _fail(path, f"must have type {expected!r}; got {type(instance).__name__}")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                _fail(path, f"is missing required property {key!r}")

        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key in properties:
                _validate(value, properties[key], root_schema, schema_path, f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                _fail(path, f"contains unknown property {key!r}")

    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            _fail(path, f"must contain at least {schema['minItems']} item(s)")
        if schema.get("uniqueItems") and len({_freeze(item) for item in instance}) != len(instance):
            _fail(path, "must contain unique items")
        item_schema = schema.get("items")
        if item_schema:
            for index, value in enumerate(instance):
                _validate(value, item_schema, root_schema, schema_path, f"{path}[{index}]")

    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            _fail(path, f"must contain at least {schema['minLength']} character(s)")
        if schema.get("format") == "uri":
            parsed = urlparse(instance)
            if not parsed.scheme or not parsed.netloc:
                _fail(path, "must be an absolute URI")
        elif schema.get("format") == "date-time":
            try:
                datetime.fromisoformat(instance.replace("Z", "+00:00"))
            except ValueError:
                _fail(path, "must be an ISO 8601 date-time")

    if _is_number(instance) and "minimum" in schema and instance < schema["minimum"]:
        _fail(path, f"must be at least {schema['minimum']}")
    if _is_number(instance) and "maximum" in schema and instance > schema["maximum"]:
        _fail(path, f"must be at most {schema['maximum']}")


def _resolve_ref(
    reference: str,
    root_schema: dict[str, Any],
    schema_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    if reference.startswith("#/"):
        target: Any = root_schema
        for part in reference[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        return target, root_schema, schema_path

    external_path = schema_path.parent / reference
    external_root = json.loads(external_path.read_text(encoding="utf-8"))
    return external_root, external_root, external_path


def _matches_type(instance: Any, expected: str | list[str]) -> bool:
    names = [expected] if isinstance(expected, str) else expected
    return any(
        {
            "object": isinstance(instance, dict),
            "array": isinstance(instance, list),
            "string": isinstance(instance, str),
            "number": _is_number(instance),
            "integer": isinstance(instance, int) and not isinstance(instance, bool),
            "null": instance is None,
            "boolean": isinstance(instance, bool),
        }.get(name, False)
        for name in names
    )


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _freeze(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _fail(path: str, message: str) -> None:
    raise SchemaValidationError(f"{path} {message}")
