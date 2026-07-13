"""ARCP — Agent Runtime Compatibility Protocol v0.2.

Public API
----------
resolve(harness, beta, agent, *, environment=None) -> dict
    Multi-component compatibility resolution.
resolve_environment(environment) -> dict
    Convenience wrapper for explicit environment dicts.
validate_compatibility_document(doc) -> list[str]
    Validate a compatibility document (auto-detects v0.1/v0.2).
validate_resolution_document(doc) -> list[str]
    Validate a resolution document (auto-detects v0.1/v0.2).
check_secrets(doc) -> list[dict]
    Recursively check for secret-like field names.
load_json_file(path) -> dict
    Load a JSON file from disk.
ARCP_SCHEMA_VERSION : str
    The current schema version constant ("0.2").
upgrade_v0_1_to_v0_2(doc) -> dict
    Convert a v0.1 document to v0.2 format.
"""

from __future__ import annotations

import json
from typing import Any

from arcp.resolver import resolve, resolve_environment
from arcp.validation import (
    check_secrets,
    is_transitional_format,
    normalize_transitional_document,
    upgrade_v0_1_to_v0_2,
    validate_document as validate_compatibility_document,
    validate_resolution as validate_resolution_document,
)
from arcp.models import SCHEMA_VERSION as ARCP_SCHEMA_VERSION

__version__ = "0.2.1"


def load_json_file(path: str) -> dict[str, Any]:
    """Load a JSON file from the filesystem."""
    with open(path) as f:
        return json.load(f)


__all__ = [
    "resolve",
    "resolve_environment",
    "validate_compatibility_document",
    "validate_resolution_document",
    "check_secrets",
    "load_json_file",
    "upgrade_v0_1_to_v0_2",
    "normalize_transitional_document",
    "is_transitional_format",
    "ARCP_SCHEMA_VERSION",
]
