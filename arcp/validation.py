"""Schema validation and secret-field detection for ARCP documents."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from jsonschema import validate as jsonschema_validate
from jsonschema.exceptions import ValidationError

from arcp.models import ALLOWED_SECRET_KEYS, SECRET_PATTERNS

_SCHEMAS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schemas")


def _load_schema(name: str) -> dict[str, Any]:
    path = os.path.join(_SCHEMAS_DIR, name)
    with open(path) as f:
        return json.load(f)


def load_compatibility_schema() -> dict[str, Any]:
    return _load_schema("compatibility_document_v0_1.schema.json")


def load_resolution_schema() -> dict[str, Any]:
    return _load_schema("compatibility_resolution_v0_1.schema.json")


def validate_document(doc: dict[str, Any]) -> list[str]:
    """Validate a compatibility document against the JSON Schema.

    Returns a list of error messages (empty = valid).
    """
    schema = load_compatibility_schema()
    errors: list[str] = []
    try:
        jsonschema_validate(doc, schema)
    except ValidationError as e:
        errors.append(f"Schema validation failed: {e.message}")
    return errors


def validate_resolution(resolution: dict[str, Any]) -> list[str]:
    """Validate a resolution document against the resolution schema."""
    schema = load_resolution_schema()
    errors: list[str] = []
    try:
        jsonschema_validate(resolution, schema)
    except ValidationError as e:
        errors.append(f"Resolution schema validation failed: {e.message}")
    return errors


def check_secrets(doc: dict[str, Any]) -> list[dict[str, str]]:
    """Recursively check for secret-like field names.

    Uses a denylist + allowlist approach:
      - Any key matching a ``SECRET_PATTERNS`` regex is flagged,
        *unless* the key is in ``ALLOWED_SECRET_KEYS``.
      - Only field *names* are scanned; values are not inspected for
        secret-like content (to avoid flagging documentation text).

    Returns a list of found issues, each with ``field`` and ``pattern`` keys.
    """
    findings: list[dict[str, str]] = []
    _check_secrets_recursive(doc, "", findings)
    return findings


def _check_secrets_recursive(
    obj: Any, path: str, findings: list[dict[str, str]]
) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            full_path = f"{path}.{key}" if path else key
            # Allowlist check: skip known-good ARCP vocabulary keys
            if key.lower() not in ALLOWED_SECRET_KEYS:
                for pattern_str in SECRET_PATTERNS:
                    if re.search(pattern_str, key, re.IGNORECASE):
                        findings.append({"field": full_path, "pattern": pattern_str})
                        break
            _check_secrets_recursive(value, full_path, findings)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _check_secrets_recursive(item, f"{path}[{i}]", findings)
