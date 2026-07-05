"""Deterministic ARCP compatibility resolver."""

from __future__ import annotations

import copy
from typing import Any

from arcp.models import get_contracts
from arcp.semver import is_broad_range, match_range


def resolve(
    harness: dict[str, Any],
    beta: dict[str, Any],
    agent: dict[str, Any],
) -> dict[str, Any]:
    """Determine whether *agent* is compatible with *harness* and *beta*.

    Returns a deterministic, JSON-serialisable resolution dict.
    """
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    suggested: list[str] = []

    # ── helpers ──────────────────────────────────────────────────────────
    def _add_blocker(b: dict[str, Any]) -> None:
        blockers.append(b)

    def _add_warning(w: dict[str, Any]) -> None:
        warnings.append(w)

    # ── 1. agent.requires.harness ↔ harness.version ──────────────────────
    agent_req_harness = _get(agent, "requires.harness")
    harness_ver = harness.get("version", "")
    if agent_req_harness and not match_range(agent_req_harness, harness_ver):
        _add_blocker(
            {
                "type": "version_mismatch",
                "required_by": "agent",
                "field": "requires.harness",
                "expected": agent_req_harness,
                "actual": harness_ver,
            }
        )

    # ── 2. agent.requires.beta ↔ beta.version (optional) ─────────────────
    agent_req_beta = _get(agent, "requires.beta")
    beta_ver = beta.get("version", "")
    if agent_req_beta and not match_range(agent_req_beta, beta_ver):
        _add_blocker(
            {
                "type": "version_mismatch",
                "required_by": "agent",
                "field": "requires.beta",
                "expected": agent_req_beta,
                "actual": beta_ver,
            }
        )

    # ── 3. beta.supports.harness ↔ harness.version ──────────────────────
    beta_supports_harness = _get(beta, "supports.harness")
    if beta_supports_harness and not match_range(beta_supports_harness, harness_ver):
        _add_blocker(
            {
                "type": "harness_unsupported_by_beta",
                "required_by": "beta",
                "expected": beta_supports_harness,
                "actual": harness_ver,
            }
        )

    # ── 4. agent required tools → provided by harness ───────────────────
    agent_tools = _str_set(agent, "tools")
    harness_tools = _str_set(harness, "tools")
    for tool in agent_tools:
        if tool not in harness_tools:
            _add_blocker(
                {
                    "type": "missing_tool",
                    "required_by": "agent",
                    "tool": tool,
                    "provided_by_harness": False,
                }
            )

    # ── 5. agent required tools → supported by beta ─────────────────────
    beta_tools = _str_set(beta, "tools")
    for tool in agent_tools:
        if tool not in beta_tools:
            _add_blocker(
                {
                    "type": "missing_tool",
                    "required_by": "agent",
                    "tool": tool,
                    "supported_by_beta": False,
                }
            )

    # ── 6. agent required capabilities → provided by harness ───────────
    agent_caps = _str_set(agent, "capabilities")
    harness_caps = _str_set(harness, "capabilities")
    for cap in agent_caps:
        if cap not in harness_caps:
            _add_blocker(
                {
                    "type": "missing_capability",
                    "required_by": "agent",
                    "capability": cap,
                    "provided_by_harness": False,
                    "supported_by_beta": False,
                }
            )

    # ── 7. agent required capabilities → supported by beta ─────────────
    beta_caps = _str_set(beta, "capabilities")
    for cap in agent_caps:
        if cap not in beta_caps:
            existing = _find_blocker(
                blockers, "missing_capability", capability=cap
            )
            if existing is not None:
                existing["supported_by_beta"] = False
            else:
                _add_blocker(
                    {
                        "type": "missing_capability",
                        "required_by": "agent",
                        "capability": cap,
                        "provided_by_harness": True,
                        "supported_by_beta": False,
                    }
                )

    # ── 8. required contract versions ──────────────────────────────────
    agent_contracts = _get(agent, "contracts")
    harness_contracts = get_contracts(harness)
    beta_contracts_raw = beta.get("contracts", [])
    beta_contract_names: set[str] = set()
    if isinstance(beta_contracts_raw, dict):
        beta_contract_names = set(beta_contracts_raw.keys())
    elif isinstance(beta_contracts_raw, list):
        beta_contract_names = {str(x) for x in beta_contracts_raw}

    if isinstance(agent_contracts, dict):
        for cname, cver in agent_contracts.items():
            if cname not in harness_contracts:
                _add_blocker(
                    {
                        "type": "missing_contract",
                        "required_by": "agent",
                        "contract": cname,
                        "provided_by_harness": False,
                    }
                )
            else:
                hv = harness_contracts[cname]
                if cver and not match_range(cver, hv):
                    _add_blocker(
                        {
                            "type": "contract_version_mismatch",
                            "required_by": "agent",
                            "contract": cname,
                            "expected": cver,
                            "actual": hv,
                        }
                    )
            if cname not in beta_contract_names:
                _add_blocker(
                    {
                        "type": "missing_contract",
                        "required_by": "agent",
                        "contract": cname,
                        "supported_by_beta": False,
                    }
                )

    # ── 9. agent required event types → emitted by harness ─────────────
    agent_events = _str_set(agent, "event_types")
    harness_events = _str_set(harness, "event_types")
    for evt in agent_events:
        if evt not in harness_events:
            _add_blocker(
                {
                    "type": "missing_event_type",
                    "required_by": "agent",
                    "event_type": evt,
                    "provided_by_harness": False,
                }
            )

    # ── 9b. agent event types → renderable by beta (warning) ──────────
    beta_events = _str_set(beta, "event_types")
    for evt in agent_events:
        if evt not in beta_events and evt in harness_events:
            _add_warning(
                {
                    "type": "event_type_not_renderable",
                    "event_type": evt,
                    "detail": f"Beta cannot display event type '{evt}'",
                }
            )

    # ── Warnings ────────────────────────────────────────────────────────
    # W1: harness capability not in beta
    for cap in harness_caps:
        if cap not in beta_caps:
            _add_warning(
                {
                    "type": "capability_not_rendered_by_beta",
                    "capability": cap,
                    "detail": f"Harness provides '{cap}' but Beta does not support it",
                }
            )

    # W2: (covered by 9b above)

    # W3: agent provider capability but beta provider_selection disabled
    beta_constraints = beta.get("constraints", {}) or {}
    if isinstance(beta_constraints, dict):
        provider_sel = beta_constraints.get("provider_selection", True)
        has_provider_cap = any(
            "provider" in c.lower() for c in agent_caps
        )
        if has_provider_cap and not provider_sel:
            _add_warning(
                {
                    "type": "provider_selection_disabled",
                    "detail": "Agent uses provider-related capability but Beta provider selection is disabled",
                }
            )

    # W4: broad version range
    for key, rng in (agent.get("requires", {}) or {}).items():
        if is_broad_range(rng):
            _add_warning(
                {
                    "type": "broad_version_range",
                    "key": key,
                    "range": rng,
                    "detail": f"Agent requires {key} {rng} which spans multiple major versions",
                }
            )

    # ── Matched items ───────────────────────────────────────────────────
    matched_tools = sorted(agent_tools & harness_tools & beta_tools)
    matched_caps = sorted(agent_caps & harness_caps & beta_caps)

    # Contracts: intersection of what the agent needs, harness provides,
    # and beta supports.
    matched_contracts: dict[str, str] = {}
    if isinstance(agent_contracts, dict):
        harness_contracts = get_contracts(harness)
        for cname in agent_contracts:
            if cname in harness_contracts and cname in beta_contract_names:
                matched_contracts[cname] = harness_contracts[cname]
    else:
        harness_contracts = get_contracts(harness)
        # No agent contract requirements → match all harness contracts
        # that beta also supports
        for cname in harness_contracts:
            if cname in beta_contract_names:
                matched_contracts[cname] = harness_contracts[cname]

    compatible = len(blockers) == 0

    result: dict[str, Any] = {
        "arcp_schema_version": "0.1",
        "compatible": compatible,
        "decision": "allowed" if compatible else "blocked",
        "resolved_versions": {
            "harness": harness_ver,
            "beta": beta_ver,
            "agent": agent.get("version", ""),
        },
        "matched": {
            "tools": matched_tools,
            "capabilities": matched_caps,
            "contracts": matched_contracts,
        },
        "warnings": warnings,
        "blockers": blockers,
    }

    if not compatible:
        result["suggested_actions"] = _generate_suggestions(blockers)

    return result


# ── internal helpers ──────────────────────────────────────────────────────


def _get(obj: dict[str, Any], dotted: str, default: Any = None) -> Any:
    parts = dotted.split(".")
    for part in parts:
        if isinstance(obj, dict):
            obj = obj.get(part, {})
        else:
            return default
    return obj if obj != {} else default


def _str_set(obj: dict[str, Any], key: str) -> set[str]:
    raw = obj.get(key)
    if isinstance(raw, list):
        return {str(x) for x in raw}
    return set()


def _find_blocker(
    blockers: list[dict[str, Any]], btype: str, **kwargs: Any
) -> dict[str, Any] | None:
    for b in blockers:
        if b.get("type") != btype:
            continue
        if all(b.get(k) == v for k, v in kwargs.items()):
            return b
    return None


def _generate_suggestions(blockers: list[dict[str, Any]]) -> list[str]:
    suggestions: list[str] = []
    for b in blockers:
        t = b.get("type", "")
        if t == "missing_capability":
            cap = b.get("capability", "")
            suggestions.append(f"Use a Harness version that provides {cap}.")
            suggestions.append(
                f"Use a Beta version that can render {cap}-related run events."
            )
        elif t == "missing_tool":
            tool = b.get("tool", "")
            suggestions.append(
                f"Ensure Harness provides tool '{tool}'."
            )
            suggestions.append(
                f"Ensure Beta supports tool '{tool}'."
            )
        elif t == "version_mismatch":
            field = b.get("field", "unknown")
            suggestions.append(
                f"Adjust the {field} version range to match the actual version."
            )
        elif t == "harness_unsupported_by_beta":
            suggestions.append(
                "Use a Harness version supported by this Beta version."
            )
        elif t == "missing_contract":
            contract = b.get("contract", "")
            suggestions.append(
                f"Ensure both Harness and Beta support contract '{contract}'."
            )
        elif t == "contract_version_mismatch":
            contract = b.get("contract", "")
            suggestions.append(
                f"Align contract '{contract}' version between agent and harness."
            )
        elif t == "missing_event_type":
            evt = b.get("event_type", "")
            suggestions.append(
                f"Ensure Harness emits event type '{evt}'."
            )
    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    return deduped
