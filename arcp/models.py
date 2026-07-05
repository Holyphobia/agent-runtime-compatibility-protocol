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

# Denylist patterns for secret-like field names.
# Each is a regex searched (re.IGNORECASE) against each key.
# Patterns are designed to catch compound keys (e.g. provider_api_key,
# my_secret_key, bearer_token) while avoiding false positives
# on legitimate ARCP vocabulary terms.
SECRET_PATTERNS = [
    r"api_key",
    r"apikey",
    r"access_key",
    r"secret_key",
    r"client_secret",
    r"access_?token",
    r"refresh_?token",
    r"bearer_?token",
    r"authorization",
    r"password",
    r"passwd",
    r"credential",
    r"private_key",
    r"^secret$",
    r"^token$",
]

# Allowlist: keys whose name passes a denylist pattern but are
# legitimate ARCP compatibility vocabulary and MUST NOT be flagged.
ALLOWED_SECRET_KEYS = frozenset({
    "secret_policy",
    "secret_ref",
    "secret_ref_only",
    "secretref",
    "provider",
    "supports_user_provider",
    "provider_selection",
    "provider_profile",
    "provider_only",
    "provider_gateway",
    "default_network",
    "human_review_supported",
})

KNOWN_CONTRACTS = frozenset({
    "agent_manifest",
    "run_request_envelope",
    "provider_profile",
    "run_event_contract",
})


def get_document_kind(doc: dict[str, Any]) -> str:
    return str(doc.get("kind", ""))


def get_contracts(doc: dict[str, Any]) -> dict[str, str]:
    """Extract contracts as a dict of name->version."""
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
