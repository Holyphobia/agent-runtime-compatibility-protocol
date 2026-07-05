"""ARCP — Agent Runtime Compatibility Protocol.

Public API
----------
resolve(harness, beta, agent) -> dict
    Deterministic compatibility resolution between three documents.
validate_compatibility_document(doc) -> list[str]
    Validate a compatibility document against the JSON Schema.
validate_resolution_document(doc) -> list[str]
    Validate a resolution against the resolution schema.
check_secrets(doc) -> list[dict]
    Recursively check for secret-like field names.
load_json_file(path) -> dict
    Load a JSON file from disk.
ARCP_SCHEMA_VERSION : str
    The current schema version constant ("0.1").
"""

from __future__ import annotations

import json
from typing import Any

from arcp.resolver import resolve
from arcp.validation import (
    check_secrets,
    validate_document as validate_compatibility_document,
    validate_resolution as validate_resolution_document,
)
from arcp.models import SCHEMA_VERSION as ARCP_SCHEMA_VERSION

__version__ = "0.1.0"


def load_json_file(path: str) -> dict[str, Any]:
    """Load a JSON file from the filesystem."""
    with open(path) as f:
        return json.load(f)


__all__ = [
    "resolve",
    "validate_compatibility_document",
    "validate_resolution_document",
    "check_secrets",
    "load_json_file",
    "ARCP_SCHEMA_VERSION",
]
