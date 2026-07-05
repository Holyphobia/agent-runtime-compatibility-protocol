from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "0.1"

DOCUMENT_KINDS = frozenset({"harness", "beta", "agent"})

REQUIRED_FIELDS = {
    "arcp_schema_version",
    "kind",
    "id",
    "version",
    "name",
    "description",
}

SECRET_PATTERNS = [
    "api_key",
    "apikey",
    r"^secret$",
    r"^token$",
    r"^password$",
    r"^bearer$",
    r"^authorization$",
]

KNOWN_CONTRACTS = frozenset({
    "agent_manifest",
    "run_request_envelope",
    "provider_profile",
    "run_event_contract",
})


def get_document_kind(doc: dict[str, Any]) -> str:
    return str(doc.get("kind", ""))


def get_contracts(doc: dict[str, Any]) -> dict[str, str]:
    """Extract contracts as a dict of name→version."""
    raw = doc.get("contracts", {})
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    if isinstance(raw, list):
        return {str(item): "" for item in raw}
    return {}


def get_supports(doc: dict[str, Any]) -> dict[str, str]:
    raw = doc.get("supports", {})
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    return {}


def get_requires(doc: dict[str, Any]) -> dict[str, str]:
    raw = doc.get("requires", {})
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    return {}
