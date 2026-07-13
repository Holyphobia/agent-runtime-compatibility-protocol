"""ARCP v0.2 data model — component types, contract families, capability vocabulary."""

from __future__ import annotations

from typing import Any

# ── Schema version ──────────────────────────────────────────────────────
SCHEMA_VERSION = "0.2"
SCHEMA_VERSION_V0_1 = "0.1"

# ── Supported component types ───────────────────────────────────────────
COMPONENT_TYPES = frozenset({
    "harness",
    "beta",
    "agent",
    "tool",
    "tool_pack",
    "llm_provider_profile",
})

DOCUMENT_KINDS = COMPONENT_TYPES  # alias for backward compat

REQUIRED_FIELDS = frozenset({
    "arcp_schema_version",
    "component_type",
    "component_id",
    "component_version",
    "protocol_version",
})

# Legacy v0.1 required fields (still needed for v0.1 compat)
LEGACY_REQUIRED_FIELDS = frozenset({
    "arcp_schema_version",
    "kind",
    "id",
    "version",
    "name",
    "description",
})

# ── Contract families ───────────────────────────────────────────────────
CONTRACT_FAMILIES = frozenset({
    "agent_manifest",
    "run_request",
    "run_result",
    "interactive_run_control",
    "run_events",
    "artifacts",
    "human_review",
    "checkpoint_resume",
    "cancellation",
    "input_schema",
    "output_schema",
})

# ── Capability vocabulary (namespaced) ──────────────────────────────────
# Canonical form: lowercase dotted notation.
# Migrated from legacy UPPER_CASE via normalization.
CANONICAL_CAPABILITIES = frozenset({
    "llm.completion",
    "web.fetch",
    "web.search",
    "web.crawl",
    "document.read",
    "file.write",
    "email.send",
    "structured_output",
})

# Legacy → canonical mapping
LEGACY_CAPABILITY_ALIASES: dict[str, str] = {
    "LLM_COMPLETION": "llm.completion",
    "WEB_FETCH": "web.fetch",
    "WEB_SEARCH": "web.search",
    "SITE_CRAWL": "web.crawl",
    "DOCUMENT_READ": "document.read",
    "FILE_WRITE": "file.write",
    "EMAIL_SEND": "email.send",
}

# ── LLM requirement fields ──────────────────────────────────────────────
LLM_REQUIREMENT_FIELDS = frozenset({
    "llm.completion",
    "minimum_context_window",
    "structured_output_required",
    "tool_calling_required",
    "streaming_optional",
    "quality_tier",
})

# ── Standard review actions ─────────────────────────────────────────────
STANDARD_REVIEW_ACTIONS = frozenset({
    "approve",
    "reject",
    "request_changes",
})

# ── Resolution decision types ───────────────────────────────────────────
DECISION_ALLOWED = "allowed"
DECISION_ALLOWED_WITH_WARNINGS = "allowed_with_warnings"
DECISION_DENIED = "denied"
DECISION_INDETERMINATE = "indeterminate"

DECISION_TYPES = frozenset({
    DECISION_ALLOWED,
    DECISION_ALLOWED_WITH_WARNINGS,
    DECISION_DENIED,
    DECISION_INDETERMINATE,
})

# ── Secret denylist ─────────────────────────────────────────────────────
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


# ── Helpers ─────────────────────────────────────────────────────────────

def get_component_type(doc: dict[str, Any]) -> str:
    """Get component type from a v0.2 or v0.1 document."""
    ct = doc.get("component_type") or doc.get("kind", "")
    return str(ct)


def get_component_id(doc: dict[str, Any]) -> str:
    return str(doc.get("component_id") or doc.get("id", ""))


def get_component_version(doc: dict[str, Any]) -> str:
    return str(doc.get("component_version") or doc.get("version", ""))


def get_protocol_version(doc: dict[str, Any]) -> str:
    return str(doc.get("protocol_version") or doc.get("arcp_schema_version", ""))


def normalize_capability(cap: str) -> str:
    """Normalize a capability identifier to canonical form."""
    lower = cap.lower().strip()
    # Check legacy alias map
    if cap in LEGACY_CAPABILITY_ALIASES:
        return LEGACY_CAPABILITY_ALIASES[cap]
    # Already dotted lowercase
    if "." in lower:
        return lower
    # Convert UPPER_CASE to dotted form via legacy map (case-insensitive)
    for legacy, canonical in LEGACY_CAPABILITY_ALIASES.items():
        if cap.upper() == legacy:
            return canonical
    # Return as-is if no mapping exists (extensibility)
    return lower


def is_v0_1_document(doc: dict[str, Any]) -> bool:
    return doc.get("arcp_schema_version") == "0.1" or "kind" in doc


def is_v0_2_document(doc: dict[str, Any]) -> bool:
    return doc.get("protocol_version") == "0.2" or doc.get("arcp_schema_version") == "0.2"
