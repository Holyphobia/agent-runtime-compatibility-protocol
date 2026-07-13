"""Schema validation and secret-field detection for ARCP documents (v0.1 and v0.2)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from jsonschema import validate as jsonschema_validate
from jsonschema.exceptions import ValidationError

from arcp.models import ALLOWED_SECRET_KEYS, SECRET_PATTERNS, is_v0_1_document

_SCHEMAS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schemas")


def _load_schema(name: str) -> dict[str, Any]:
    path = os.path.join(_SCHEMAS_DIR, name)
    with open(path) as f:
        return json.load(f)


def load_compatibility_schema(version: str = "0.2") -> dict[str, Any]:
    if version == "0.1":
        return _load_schema("compatibility_document_v0_1.schema.json")
    return _load_schema("compatibility_document_v0_2.schema.json")


def load_resolution_schema(version: str = "0.2") -> dict[str, Any]:
    if version == "0.1":
        return _load_schema("compatibility_resolution_v0_1.schema.json")
    return _load_schema("compatibility_resolution_v0_2.schema.json")


def _detect_schema_version(doc: dict[str, Any]) -> str:
    """Detect whether a document is v0.1 or v0.2."""
    if is_v0_1_document(doc):
        return "0.1"
    return "0.2"


def validate_document(doc: dict[str, Any]) -> list[str]:
    """Validate a compatibility document against the appropriate JSON Schema.

    Auto-detects v0.1 vs v0.2 based on document fields.
    Returns a list of error messages (empty = valid).
    """
    version = _detect_schema_version(doc)
    try:
        schema = load_compatibility_schema(version)
    except FileNotFoundError:
        return [f"Schema file not found for version {version}"]
    errors: list[str] = []
    try:
        jsonschema_validate(doc, schema)
    except ValidationError as e:
        errors.append(f"Schema validation failed: {e.message}")
    return errors


def validate_resolution(resolution: dict[str, Any]) -> list[str]:
    """Validate a resolution document against the resolution schema.

    Auto-detects v0.1 vs v0.2.
    """
    version = _detect_schema_version(resolution)
    try:
        schema = load_resolution_schema(version)
    except FileNotFoundError:
        return [f"Schema file not found for version {version}"]
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
            if key.lower() not in ALLOWED_SECRET_KEYS:
                for pattern_str in SECRET_PATTERNS:
                    if re.search(pattern_str, key, re.IGNORECASE):
                        findings.append({"field": full_path, "pattern": pattern_str})
                        break
            _check_secrets_recursive(value, full_path, findings)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _check_secrets_recursive(item, f"{path}[{i}]", findings)


def upgrade_v0_1_to_v0_2(doc: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a v0.1 document to v0.2 internal representation."""
    new: dict[str, Any] = {
        "arcp_schema_version": "0.2",
        "component_type": doc.get("kind", "unknown"),
        "component_id": doc.get("id", ""),
        "component_version": doc.get("version", ""),
        "protocol_version": "0.2",
        "name": doc.get("name", ""),
        "description": doc.get("description", ""),
    }

    contracts = doc.get("contracts", {})
    if isinstance(contracts, list):
        new["contracts"] = {c: "0" for c in contracts}
    elif isinstance(contracts, dict):
        new["contracts"] = contracts

    tools = doc.get("tools", [])
    if tools:
        new["tools"] = tools

    caps = doc.get("capabilities", [])
    if caps:
        new["capabilities"] = {"provides": caps}

    events = doc.get("event_types", [])
    if events:
        new["events"] = {"supported_types": events}

    requires = doc.get("requires", {})
    if requires:
        new["requires"] = requires

    supports = doc.get("supports", {})
    if supports:
        new["supports"] = supports

    constraints = doc.get("constraints", {})
    if constraints:
        new["constraints"] = constraints

    return new
