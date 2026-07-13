"""ARCP v0.2 multi-component compatibility resolver.

Supports environment-level resolution across harness, beta, agent(s),
tool/tool-pack(s), and LLM provider profile(s).
"""

from __future__ import annotations

from typing import Any

from arcp.models import (
    CANONICAL_CAPABILITIES,
    CONTRACT_FAMILIES,
    DECISION_ALLOWED,
    DECISION_ALLOWED_WITH_WARNINGS,
    DECISION_DENIED,
    DECISION_INDETERMINATE,
    LEGACY_CAPABILITY_ALIASES,
    SCHEMA_VERSION,
    get_component_id,
    get_component_type,
    get_component_version,
    get_protocol_version,
    is_v0_1_document,
    normalize_capability,
)
from arcp.semver import is_broad_range, match_range

# ── Public API ──────────────────────────────────────────────────────────


def resolve(
    harness: dict[str, Any] | None = None,
    beta: dict[str, Any] | None = None,
    agent: dict[str, Any] | None = None,
    *,
    environment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve compatibility within a multi-component environment.

    Two calling conventions:

    1. Legacy: ``resolve(harness, beta, agent)`` — 3-party v0.1-style.
    2. Environment: ``resolve(environment={...})`` — explicit env dict.

    The environment dict may contain:
        harness: dict
        beta: dict
        agents: list[dict]  or  agent: dict
        tools: list[dict]
        tool_packs: list[dict]
        provider: dict  or  providers: list[dict]
    """
    if environment is not None:
        env = _normalize_environment(environment)
    else:
        env = _normalize_environment({
            "harness": harness,
            "beta": beta,
            "agent": agent,
        })

    # Detect v0.1 → use legacy resolver (only if actual v0.1 docs exist)
    all_docs = _collect_docs(env)
    v0_1_docs = [v for v in all_docs if v is not None and is_v0_1_document(v)]
    if v0_1_docs and len(v0_1_docs) == len([v for v in all_docs if v is not None]):
        return _legacy_resolve(env)

    return _v0_2_resolve(env)


def resolve_environment(environment: dict[str, Any]) -> dict[str, Any]:
    """Convenience wrapper: resolve an explicit environment dict."""
    return resolve(environment=environment)


# ── v0.2 resolver ───────────────────────────────────────────────────────


def _v0_2_resolve(env: _Environment) -> dict[str, Any]:
    result: dict[str, Any] = {
        "arcp_schema_version": SCHEMA_VERSION,
        "compatible": False,
        "decision": DECISION_DENIED,
        "resolved_versions": {},
        "matched_components": [],
        "matched_contracts": {},
        "matched_capabilities": [],
        "missing_required_capabilities": [],
        "missing_optional_capabilities": [],
        "incompatible_contracts": [],
        "unknown_capabilities": [],
        "warnings": [],
        "blockers": [],
        "reasons": [],
        "remediation": [],
    }

    harness = env.harness
    beta = env.beta
    agents = env.agents
    tools = env.tools
    tool_packs = env.tool_packs
    provider = env.provider

    # Collect all tool-provided capabilities
    tool_capabilities: set[str] = set()
    for t in tools:
        tc = _get_capabilities_provides(t)
        tool_capabilities.update(tc)
    for tp in tool_packs:
        tc = _get_capabilities_provides(tp)
        tool_capabilities.update(tc)

    # Record resolved versions
    _set_version(result, "harness", harness)
    _set_version(result, "beta", beta)
    for i, a in enumerate(agents):
        _set_version(result, f"agent_{i}" if len(agents) > 1 else "agent", a)
    for i, t in enumerate(tools):
        _set_version(result, f"tool_{i}", t)
    for i, tp in enumerate(tool_packs):
        _set_version(result, f"tool_pack_{i}", tp)
    if provider:
        _set_version(result, "provider", provider)

    blockers: list[dict[str, Any]] = []
    warnings_list: list[str] = []
    remediation_list: list[str] = []
    reasons: list[str] = []

    # ── Stage 1: validate document structure ──────────────────────────
    if harness is None:
        blockers.append({"type": "missing_component", "component": "harness"})
        remediation_list.append("A harness component is required.")
    if not agents:
        blockers.append({"type": "missing_component", "component": "agent"})
        remediation_list.append("At least one agent component is required.")
    if blockers:
        _finalize(result, blockers, warnings_list, reasons, remediation_list)
        return result

    for a in agents:
        _check_contract_field_types(a, blockers, remediation_list)

    # ── Stage 2: component identity ───────────────────────────────────
    result["matched_components"] = _resolve_identities(env)

    # ── Stage 3: harness ↔ agent version requirements ─────────────────
    for a in agents:
        _resolve_harness_requirement(a, harness, blockers, remediation_list)
        if beta:
            _resolve_beta_requirement(a, beta, blockers, remediation_list)
        _resolve_agent_contracts(a, harness, beta, blockers, reasons, remediation_list, warnings_list)

    if beta and harness:
        _beta_supports_harness(beta, harness, blockers, remediation_list)

    # ── Stage 4: capabilities ─────────────────────────────────────────
    harness_caps = _get_capabilities_provides(harness)
    beta_caps = _get_capabilities_provides(beta)
    all_provided: set[str] = set()
    all_provided.update(harness_caps)
    all_provided.update(beta_caps)
    all_provided.update(tool_capabilities)

    all_missing_required: set[str] = set()
    all_missing_optional: set[str] = set()
    all_unknown: set[str] = set()

    for a in agents:
        required = _get_set(a, "capabilities", "required")
        optional = _get_set(a, "capabilities", "optional")
        agent_req_tools = _get_set(a, "tools")

        # Tool requirements: agent requires tool → must be in harness or tools
        harness_tools = _safe_list(harness, "tools")
        all_avail_tools = set(harness_tools)
        for t in tools:
            all_avail_tools.update(_safe_list(t, "tools"))
        for tp in tool_packs:
            all_avail_tools.update(_safe_list(tp, "tools"))

        for tool in agent_req_tools:
            if tool not in all_avail_tools:
                blockers.append({
                    "type": "missing_tool",
                    "tool": tool,
                    "detail": f"Agent requires tool '{tool}' which is not available",
                })
                remediation_list.append(f"Ensure a tool providing '{tool}' is installed.")

        # Capability normalization
        for cap in required:
            ncap = normalize_capability(cap)
            if ncap not in all_provided and ncap not in tool_capabilities:
                all_missing_required.add(ncap)
                reasons.append(f"Agent requires {ncap} but no component provides it.")
            # Check if capability is known
            if ncap not in CANONICAL_CAPABILITIES and ncap not in LEGACY_CAPABILITY_ALIASES.values():
                all_unknown.add(ncap)

        for cap in optional:
            ncap = normalize_capability(cap)
            if ncap not in all_provided and ncap not in tool_capabilities:
                all_missing_optional.add(ncap)
                warnings_list.append(f"Optional capability {ncap} is not available.")
            if ncap not in CANONICAL_CAPABILITIES and ncap not in LEGACY_CAPABILITY_ALIASES.values():
                all_unknown.add(ncap)

    result["missing_required_capabilities"] = sorted(all_missing_required)
    result["missing_optional_capabilities"] = sorted(all_missing_optional)
    result["unknown_capabilities"] = sorted(all_unknown)

    # Compute matched capabilities: required caps that ARE provided
    all_required_caps: set[str] = set()
    for a in agents:
        for cap in _get_set(a, "capabilities", "required"):
            all_required_caps.add(normalize_capability(cap))
    matched_caps = all_required_caps - all_missing_required - all_unknown
    result["matched_capabilities"] = sorted(matched_caps)

    if all_missing_required:
        for cap in sorted(all_missing_required):
            blockers.append({
                "type": "missing_capability",
                "capability": cap,
                "required": True,
            })
            remediation_list.append(
                f"Install a tool or use a harness that provides '{cap}'."
            )

    # ── Stage 5: provider / LLM requirements ──────────────────────────
    if provider:
        for a in agents:
            _resolve_provider(a, provider, blockers, warnings_list, reasons, remediation_list)
    else:
        for a in agents:
            if _agent_has_llm_requirements(a):
                warnings_list.append(
                    "Agent has LLM requirements but no provider profile is selected."
                )

    # ── Stage 6: Beta rendering/control support ───────────────────────
    if beta and agents:
        _resolve_beta_support(beta, agents, harness, warnings_list, remediation_list)

    # ── Stage 7: explicit incompatibilities ───────────────────────────
    for a in agents:
        incomp = _safe_list(a, "incompatibilities")
        for inc in incomp:
            blockers.append({
                "type": "explicit_incompatibility",
                "detail": inc,
            })
            remediation_list.append(f"Resolve declared incompatibility: {inc}")

    # ── Final decision ────────────────────────────────────────────────
    _finalize(result, blockers, warnings_list, reasons, remediation_list)
    return result


# ── v0.1 legacy resolver (preserved behavior) ───────────────────────────


def _legacy_resolve(env: _Environment) -> dict[str, Any]:
    """v0.1-style 3-party resolution preserving v0.1 output format."""
    harness = env.harness or {}
    beta = env.beta or {}
    agents = env.agents
    agent = agents[0] if agents else {}

    blockers: list[dict[str, Any]] = []
    warnings_list: list[dict[str, Any]] = []
    suggestions: list[str] = []

    h_ver = harness.get("component_version") or harness.get("version", "")
    b_ver = beta.get("component_version") or beta.get("version", "")
    agent_ver = agent.get("component_version") or agent.get("version", "")

    # 1. agent requires.harness
    agent_req_h = _get_dotted(agent, "requires.harness")
    if agent_req_h and not match_range(agent_req_h, h_ver):
        blockers.append({
            "type": "version_mismatch", "required_by": "agent",
            "field": "requires.harness", "expected": agent_req_h, "actual": h_ver,
        })

    # 2. agent requires.beta
    agent_req_b = _get_dotted(agent, "requires.beta")
    if agent_req_b and not match_range(agent_req_b, b_ver):
        blockers.append({
            "type": "version_mismatch", "required_by": "agent",
            "field": "requires.beta", "expected": agent_req_b, "actual": b_ver,
        })

    # 3. beta supports.harness
    beta_supports_h = _get_dotted(beta, "supports.harness")
    if beta_supports_h and not match_range(beta_supports_h, h_ver):
        blockers.append({
            "type": "harness_unsupported_by_beta",
            "expected": beta_supports_h, "actual": h_ver,
        })

    # 4. agent tools
    agent_tools = _str_set_legacy(agent, "tools")
    harness_tools = _str_set_legacy(harness, "tools")
    beta_tools = _str_set_legacy(beta, "tools")
    for tool in agent_tools:
        if tool not in harness_tools:
            blockers.append({
                "type": "missing_tool", "required_by": "agent",
                "tool": tool, "provided_by_harness": False,
            })
        if tool not in beta_tools:
            blockers.append({
                "type": "missing_tool", "required_by": "agent",
                "tool": tool, "supported_by_beta": False,
            })

    # 5. agent capabilities
    agent_caps = _str_set_legacy(agent, "capabilities")
    harness_caps = _str_set_legacy(harness, "capabilities")
    beta_caps = _str_set_legacy(beta, "capabilities")
    for cap in agent_caps:
        if cap not in harness_caps:
            blockers.append({
                "type": "missing_capability", "required_by": "agent",
                "capability": cap, "provided_by_harness": False,
                "supported_by_beta": False,
            })
        elif cap not in beta_caps:
            blockers.append({
                "type": "missing_capability", "required_by": "agent",
                "capability": cap, "provided_by_harness": True,
                "supported_by_beta": False,
            })

    # 6. contracts
    agent_contracts = _get_dotted(agent, "contracts") or {}
    harness_contracts = harness.get("contracts", {}) or {}
    beta_contracts_raw = beta.get("contracts", []) or []
    beta_contract_names: set[str] = set()
    if isinstance(beta_contracts_raw, dict):
        beta_contract_names = set(beta_contracts_raw.keys())
    elif isinstance(beta_contracts_raw, list):
        beta_contract_names = {str(x) for x in beta_contracts_raw}

    matched_contracts: dict[str, str] = {}
    if isinstance(agent_contracts, dict) and agent_contracts:
        for cname, cver in agent_contracts.items():
            if cname not in harness_contracts:
                blockers.append({
                    "type": "missing_contract", "required_by": "agent",
                    "contract": cname, "provided_by_harness": False,
                })
            else:
                hv = harness_contracts[cname]
                if cver and not match_range(cver, hv):
                    blockers.append({
                        "type": "contract_version_mismatch",
                        "required_by": "agent", "contract": cname,
                        "expected": cver, "actual": hv,
                    })
                matched_contracts[cname] = hv
            if cname not in beta_contract_names:
                blockers.append({
                    "type": "missing_contract", "required_by": "agent",
                    "contract": cname, "supported_by_beta": False,
                })
    else:
        # No agent contract requirements → match all harness contracts
        # that beta also supports (v0.1 backward compat)
        for cname, cver in harness_contracts.items():
            if cname in beta_contract_names:
                matched_contracts[cname] = cver

    # 7. event types
    agent_events = _str_set_legacy(agent, "event_types")
    harness_events = _str_set_legacy(harness, "event_types")
    for evt in agent_events:
        if evt not in harness_events:
            blockers.append({
                "type": "missing_event_type", "required_by": "agent",
                "event_type": evt, "provided_by_harness": False,
            })

    # 8. event type renderable warnings
    beta_events = _str_set_legacy(beta, "event_types")
    for evt in agent_events:
        if evt not in beta_events and evt in harness_events:
            warnings_list.append({
                "type": "event_type_not_renderable",
                "event_type": evt,
                "detail": f"Beta cannot display event type '{evt}'",
            })

    # Legacy warning: capability not rendered by beta
    for cap in harness_caps:
        if cap not in beta_caps:
            warnings_list.append({
                "type": "capability_not_rendered_by_beta",
                "capability": cap,
                "detail": f"Harness provides '{cap}' but Beta does not support it",
            })

    # Provider selection warning
    beta_constraints = beta.get("constraints", {}) or {}
    if isinstance(beta_constraints, dict):
        provider_sel = beta_constraints.get("provider_selection", True)
        has_provider_cap = any("provider" in c.lower() for c in agent_caps)
        if has_provider_cap and not provider_sel:
            warnings_list.append({
                "type": "provider_selection_disabled",
                "detail": "Agent uses provider-related capability but Beta provider selection is disabled",
            })

    # Broad version range warning
    for key, rng in (agent.get("requires", {}) or {}).items():
        if is_broad_range(rng):
            warnings_list.append({
                "type": "broad_version_range",
                "key": key, "range": rng,
                "detail": f"Agent requires {key} {rng} which spans multiple major versions",
            })

    # Matched items
    matched_tools_final = sorted(agent_tools & harness_tools & beta_tools)
    matched_caps_final = sorted(agent_caps & harness_caps & beta_caps)

    compatible = len(blockers) == 0

    result: dict[str, Any] = {
        "arcp_schema_version": "0.1",
        "compatible": compatible,
        "decision": "allowed" if compatible else "blocked",
        "resolved_versions": {
            "harness": h_ver,
            "beta": b_ver,
            "agent": agent_ver,
        },
        "matched": {
            "tools": matched_tools_final,
            "capabilities": matched_caps_final,
            "contracts": matched_contracts,
        },
        "warnings": warnings_list,
        "blockers": blockers,
    }

    if not compatible:
        result["suggested_actions"] = _generate_suggestions_legacy(blockers)

    return result


# ── Environment model ───────────────────────────────────────────────────


class _Environment:
    """Normalized internal representation of a multi-component environment."""

    def __init__(self) -> None:
        self.harness: dict[str, Any] | None = None
        self.beta: dict[str, Any] | None = None
        self.agents: list[dict[str, Any]] = []
        self.tools: list[dict[str, Any]] = []
        self.tool_packs: list[dict[str, Any]] = []
        self.provider: dict[str, Any] | None = None
        self.providers: list[dict[str, Any]] = []


def _normalize_environment(env: dict[str, Any]) -> _Environment:
    result = _Environment()

    # Harness
    raw_h = env.get("harness")
    if raw_h is not None:
        result.harness = raw_h

    # Beta
    raw_b = env.get("beta")
    if raw_b is not None:
        result.beta = raw_b

    # Agents
    raw_a = env.get("agents") or env.get("agent")
    if raw_a is not None:
        if isinstance(raw_a, list):
            result.agents = raw_a
        else:
            result.agents = [raw_a]

    # Tools
    raw_t = env.get("tools", [])
    if isinstance(raw_t, list):
        result.tools = raw_t

    # Tool packs
    raw_tp = env.get("tool_packs", [])
    if isinstance(raw_tp, list):
        result.tool_packs = raw_tp

    # Provider
    raw_p = env.get("provider") or env.get("providers")
    if raw_p is not None:
        if isinstance(raw_p, list):
            result.providers = raw_p
            result.provider = raw_p[0] if raw_p else None
        else:
            result.provider = raw_p
            result.providers = [raw_p]

    return result


def _collect_docs(env: _Environment) -> list[dict[str, Any] | None]:
    docs: list[dict[str, Any] | None] = [env.harness, env.beta]
    docs.extend(env.agents)
    return docs


# ── Stage resolvers ─────────────────────────────────────────────────────


def _resolve_identities(env: _Environment) -> list[str]:
    matched: list[str] = []
    if env.harness:
        matched.append(
            f"harness:{get_component_id(env.harness)}:{get_component_version(env.harness)}"
        )
    if env.beta:
        matched.append(
            f"beta:{get_component_id(env.beta)}:{get_component_version(env.beta)}"
        )
    for a in env.agents:
        matched.append(
            f"agent:{get_component_id(a)}:{get_component_version(a)}"
        )
    for t in env.tools:
        matched.append(
            f"tool:{get_component_id(t)}:{get_component_version(t)}"
        )
    for tp in env.tool_packs:
        matched.append(
            f"tool_pack:{get_component_id(tp)}:{get_component_version(tp)}"
        )
    if env.provider:
        matched.append(
            f"provider:{get_component_id(env.provider)}:{get_component_version(env.provider)}"
        )
    return matched


def _resolve_harness_requirement(
    agent: dict[str, Any],
    harness: dict[str, Any],
    blockers: list[dict[str, Any]],
    remediation: list[str],
) -> None:
    req_h = _get_dotted(agent, "requires.harness")
    h_ver = get_component_version(harness)
    if req_h and not match_range(req_h, h_ver):
        blockers.append({
            "type": "version_mismatch",
            "required_by": f"agent:{get_component_id(agent)}",
            "field": "requires.harness",
            "expected": req_h,
            "actual": h_ver,
        })
        remediation.append(
            f"Agent '{get_component_id(agent)}' requires harness {req_h} "
            f"but version is {h_ver}."
        )


def _resolve_beta_requirement(
    agent: dict[str, Any],
    beta: dict[str, Any],
    blockers: list[dict[str, Any]],
    remediation: list[str],
) -> None:
    req_b = _get_dotted(agent, "requires.beta")
    b_ver = get_component_version(beta)
    if req_b and not match_range(req_b, b_ver):
        blockers.append({
            "type": "version_mismatch",
            "required_by": f"agent:{get_component_id(agent)}",
            "field": "requires.beta",
            "expected": req_b,
            "actual": b_ver,
        })
        remediation.append(
            f"Agent '{get_component_id(agent)}' requires beta {req_b} "
            f"but version is {b_ver}."
        )


def _beta_supports_harness(
    beta: dict[str, Any],
    harness: dict[str, Any],
    blockers: list[dict[str, Any]],
    remediation: list[str],
) -> None:
    beta_supports = _get_dotted(beta, "supports.harness")
    h_ver = get_component_version(harness)
    if beta_supports and not match_range(beta_supports, h_ver):
        blockers.append({
            "type": "harness_unsupported_by_beta",
            "expected": beta_supports,
            "actual": h_ver,
        })
        remediation.append(
            f"Beta supports harness {beta_supports} but version is {h_ver}."
        )


def _resolve_agent_contracts(
    agent: dict[str, Any],
    harness: dict[str, Any] | None,
    beta: dict[str, Any] | None,
    blockers: list[dict[str, Any]],
    reasons: list[str],
    remediation: list[str],
    warnings_list: list[str] | None = None,
) -> None:
    agent_contracts = agent.get("contracts", {}) or {}
    if not isinstance(agent_contracts, dict):
        return

    harness_contracts = harness.get("contracts", {}) if harness else {}
    beta_contracts = beta.get("contracts", {}) if beta else {}
    if isinstance(beta_contracts, list):
        beta_contracts = {c: "0" for c in beta_contracts}

    for cname, cver in agent_contracts.items():
        if harness and cname not in harness_contracts:
            blockers.append({
                "type": "missing_contract",
                "contract": cname,
                "provided_by_harness": False,
            })
            reasons.append(f"Harness does not provide contract '{cname}'.")
            remediation.append(
                f"Use a harness version that provides contract '{cname}'."
            )
        elif harness:
            hv = harness_contracts.get(cname, "")
            if cver and not match_range(cver, hv):
                blockers.append({
                    "type": "contract_version_mismatch",
                    "contract": cname,
                    "expected": cver,
                    "actual": hv,
                    "provider": "harness",
                })
                reasons.append(
                    f"Harness contract '{cname}' version {hv} "
                    f"does not satisfy agent requirement {cver}."
                )

        if beta and cname not in beta_contracts:
            warnings_list.append(
                f"Beta does not declare support for contract '{cname}'. "
                f"Generic fallback may apply."
            )


def _resolve_provider(
    agent: dict[str, Any],
    provider: dict[str, Any],
    blockers: list[dict[str, Any]],
    warnings_list: list[str],
    reasons: list[str],
    remediation: list[str],
) -> None:
    llm_reqs = agent.get("llm_requirements", {}) or {}
    provider_caps = provider.get("provider", {}).get("capabilities", []) or provider.get("capabilities", [])
    if isinstance(provider_caps, list):
        provider_caps_set = {normalize_capability(c) for c in provider_caps}
    else:
        provider_caps_set = set()

    provider_info = provider.get("provider", {}) or provider

    # Check required LLM capabilities
    req_llm_caps = llm_reqs.get("capabilities", [])
    for cap in req_llm_caps:
        ncap = normalize_capability(cap)
        if ncap not in provider_caps_set:
            blockers.append({
                "type": "provider_missing_capability",
                "capability": ncap,
                "detail": f"Provider does not provide '{ncap}'",
            })
            reasons.append(
                f"Agent requires LLM capability '{ncap}' "
                f"but selected provider does not provide it."
            )
            remediation.append(
                f"Select a provider that supports '{ncap}'."
            )

    # Check structured output
    if llm_reqs.get("structured_output_required"):
        supports_so = provider_info.get("supports_structured_output", False)
        if not supports_so:
            # Unknown = indeterminate
            if supports_so is None:
                reasons.append(
                    "Provider capability for structured output is unknown."
                )
            else:
                blockers.append({
                    "type": "provider_lacks_capability",
                    "capability": "structured_output",
                    "detail": "Provider does not support structured output.",
                })
                remediation.append(
                    "Select a provider that supports structured output."
                )

    # Check tool calling
    if llm_reqs.get("tool_calling_required"):
        supports_tc = provider_info.get("supports_tool_calling", False)
        if not supports_tc:
            if supports_tc is None:
                reasons.append(
                    "Provider capability for tool calling is unknown."
                )
            else:
                blockers.append({
                    "type": "provider_lacks_capability",
                    "capability": "tool_calling",
                    "detail": "Provider does not support tool calling.",
                })
                remediation.append(
                    "Select a provider that supports tool calling."
                )

    # Check context window
    min_window = llm_reqs.get("minimum_context_window")
    if min_window:
        prov_window = provider_info.get("context_window", 0)
        if prov_window and prov_window < min_window:
            warnings_list.append(
                f"Provider context window ({prov_window}) is smaller "
                f"than agent minimum ({min_window})."
            )

    # Unknown mandatory capabilities → indeterminate
    for cap in req_llm_caps:
        ncap = normalize_capability(cap)
        if ncap not in CANONICAL_CAPABILITIES and ncap not in provider_caps_set:
            reasons.append(
                f"Provider capability '{ncap}' status is unknown."
            )


def _resolve_beta_support(
    beta: dict[str, Any],
    agents: list[dict[str, Any]],
    harness: dict[str, Any] | None,
    warnings_list: list[str],
    remediation: list[str],
) -> None:
    """Validate that Beta can render/control what agents need."""
    beta_artifacts = beta.get("artifacts", {}) or {}
    beta_review = beta.get("human_review", {}) or {}
    beta_events = beta.get("events", {}) or {}
    beta_caps = _get_set(beta, "capabilities", "provides")

    for a in agents:
        events = _get_set(a, "events", "supported_types") or _str_set_legacy(a, "event_types")
        for evt in events:
            beta_supported = _get_set(beta, "events", "supported_types")
            if evt not in beta_supported:
                warnings_list.append(
                    f"Beta may not display event type '{evt}' "
                    f"(generic fallback may apply)."
                )

        # Artifact support
        agent_artifact_ver = _get_dotted(a, "artifacts.schema_version")
        if agent_artifact_ver:
            beta_artifact_ver = beta_artifacts.get("schema_version", "")
            if beta_artifact_ver and not match_range(agent_artifact_ver, beta_artifact_ver):
                warnings_list.append(
                    f"Beta artifact schema version {beta_artifact_ver} does not "
                    f"satisfy agent requirement {agent_artifact_ver}."
                )

        # Review support
        agent_review_ver = _get_dotted(a, "human_review.schema_version")
        if agent_review_ver:
            beta_review_ver = beta_review.get("schema_version", "")
            if beta_review_ver and not match_range(agent_review_ver, beta_review_ver):
                warnings_list.append(
                    f"Beta review schema version {beta_review_ver} does not "
                    f"satisfy agent requirement {agent_review_ver}."
                )

        # Check renderer hints for artifacts
        agent_renderer_hints = _safe_list(a, "artifacts", "renderer_hints") or []
        beta_renderer_hints = _safe_list(beta, "artifacts", "renderer_hints") or []
        for hint in agent_renderer_hints:
            if hint not in beta_renderer_hints and "markdown" in beta_renderer_hints:
                # Generic fallback available → warning not blocker
                warnings_list.append(
                    f"Agent requested renderer '{hint}' not in Beta; "
                    f"generic fallback available."
                )
            elif hint not in beta_renderer_hints:
                warnings_list.append(
                    f"Agent requested renderer '{hint}' not supported by Beta."
                )


# ── Helpers ─────────────────────────────────────────────────────────────


def _get_capabilities_provides(doc: dict[str, Any] | None) -> set[str]:
    if doc is None:
        return set()
    caps = doc.get("capabilities", {})
    if isinstance(caps, dict):
        raw = caps.get("provides", [])
        if isinstance(raw, list):
            return {normalize_capability(c) for c in raw}
        return set()
    if isinstance(caps, list):
        return {normalize_capability(c) for c in caps}
    return set()


def _get_set(doc: dict[str, Any] | None, *keys: str) -> set[str]:
    if doc is None:
        return set()
    obj: Any = doc
    for k in keys:
        if isinstance(obj, dict):
            obj = obj.get(k, {})
        else:
            return set()
    if isinstance(obj, list):
        return {str(x) for x in obj}
    return set()


def _str_set_legacy(obj: dict[str, Any], key: str) -> set[str]:
    raw = obj.get(key)
    if isinstance(raw, list):
        return {str(x) for x in raw}
    return set()


def _get_dotted(obj: dict[str, Any] | None, dotted: str, default: Any = None) -> Any:
    if obj is None:
        return default
    parts = dotted.split(".")
    for part in parts:
        if isinstance(obj, dict):
            obj = obj.get(part)
            if obj is None:
                return default
        else:
            return default
    return obj if obj is not None else default


def _safe_list(doc: Any, *keys: str) -> list[Any]:
    if not isinstance(doc, dict):
        return []
    obj: Any = doc
    for k in keys:
        if isinstance(obj, dict):
            obj = obj.get(k, [])
        else:
            return []
    if isinstance(obj, list):
        return obj
    return []


def _set_version(
    result: dict[str, Any],
    key: str,
    doc: dict[str, Any] | None,
) -> None:
    if doc is not None:
        ver = get_component_version(doc)
        result["resolved_versions"][key] = ver


def _check_contract_field_types(
    agent: dict[str, Any],
    blockers: list[dict[str, Any]],
    remediation: list[str],
) -> None:
    contracts = agent.get("contracts", {})
    if isinstance(contracts, dict):
        for cname, cver in contracts.items():
            if cname not in CONTRACT_FAMILIES:
                blockers.append({
                    "type": "unknown_contract_family",
                    "contract": cname,
                    "detail": f"'{cname}' is not a recognized contract family",
                })
                remediation.append(
                    f"Use a recognized contract family name. "
                    f"Known: {', '.join(sorted(CONTRACT_FAMILIES))}."
                )


def _agent_has_llm_requirements(agent: dict[str, Any]) -> bool:
    llm = agent.get("llm_requirements", {}) or {}
    return bool(llm.get("capabilities")) or bool(llm.get("structured_output_required"))


def _finalize(
    result: dict[str, Any],
    blockers: list[dict[str, Any]],
    warnings_list: list[str],
    reasons: list[str],
    remediation: list[str],
) -> None:
    result["blockers"] = blockers
    result["warnings"] = warnings_list
    result["reasons"] = reasons

    if blockers:
        result["compatible"] = False
        has_indeterminate = any(
            b.get("type") == "provider_missing_capability"
            and "unknown" in b.get("detail", "").lower()
            for b in blockers
        )
        if has_indeterminate:
            result["decision"] = DECISION_INDETERMINATE
        else:
            result["decision"] = DECISION_DENIED
        _generate_remediation_from_blockers(blockers, remediation)
    elif warnings_list:
        result["compatible"] = True
        result["decision"] = DECISION_ALLOWED_WITH_WARNINGS
    else:
        result["compatible"] = True
        result["decision"] = DECISION_ALLOWED

    # Check for unknown required capabilities → indeterminate
    if result.get("unknown_capabilities") and result["decision"] != DECISION_DENIED:
        for cap in result["unknown_capabilities"]:
            if cap in result.get("missing_required_capabilities", []):
                result["decision"] = DECISION_INDETERMINATE
                result["compatible"] = False

    # Check for unknown provider capabilities → indeterminate
    unknown_reasons = [r for r in reasons if "unknown" in r.lower() and "capability" in r.lower()]
    if unknown_reasons and result["compatible"]:
        result["decision"] = DECISION_INDETERMINATE
        result["compatible"] = False
    elif unknown_reasons and result["decision"] == DECISION_DENIED:
        result["decision"] = DECISION_INDETERMINATE

    result["remediation"] = remediation


def _generate_remediation_from_blockers(
    blockers: list[dict[str, Any]],
    remediation: list[str],
) -> None:
    for b in blockers:
        btype = b.get("type", "")
        if btype == "missing_capability":
            cap = b.get("capability", "")
            remediation.append(
                f"Install a tool or use a harness that provides '{cap}'."
            )
        elif btype == "missing_tool":
            tool = b.get("tool", "")
            remediation.append(f"Ensure tool '{tool}' is installed.")
        elif btype == "version_mismatch":
            field = b.get("field", "unknown")
            remediation.append(f"Adjust {field} version requirement.")
        elif btype == "harness_unsupported_by_beta":
            remediation.append(
                "Use a harness version supported by this beta version."
            )
        elif btype == "missing_contract":
            contract = b.get("contract", "")
            remediation.append(
                f"Ensure both harness and beta support contract '{contract}'."
            )
        elif btype == "contract_version_mismatch":
            contract = b.get("contract", "")
            remediation.append(
                f"Align contract '{contract}' version between components."
            )
        elif btype == "missing_event_type":
            evt = b.get("event_type", "")
            remediation.append(
                f"Ensure harness emits event type '{evt}'."
            )
        elif btype == "provider_missing_capability":
            cap = b.get("capability", "")
            remediation.append(
                f"Select a provider that supports '{cap}'."
            )
        elif btype == "provider_lacks_capability":
            cap = b.get("capability", "")
            remediation.append(
                f"Select a provider that supports '{cap}'."
            )

    # Deduplicate
    seen: set[str] = set()
    deduped: list[str] = []
    for item in remediation:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    remediation.clear()
    remediation.extend(deduped)


def _generate_suggestions_legacy(blockers: list[dict[str, Any]]) -> list[str]:
    """Legacy v0.1 suggestion generator matching old format."""
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
            suggestions.append(f"Ensure Harness provides tool '{tool}'.")
            suggestions.append(f"Ensure Beta supports tool '{tool}'.")
        elif t == "version_mismatch":
            field = b.get("field", "unknown")
            suggestions.append(f"Adjust the {field} version range to match the actual version.")
        elif t == "harness_unsupported_by_beta":
            suggestions.append("Use a Harness version supported by this Beta version.")
        elif t == "missing_contract":
            contract = b.get("contract", "")
            suggestions.append(f"Ensure both Harness and Beta support contract '{contract}'.")
        elif t == "contract_version_mismatch":
            contract = b.get("contract", "")
            suggestions.append(f"Align contract '{contract}' version between agent and harness.")
        elif t == "missing_event_type":
            evt = b.get("event_type", "")
            suggestions.append(f"Ensure Harness emits event type '{evt}'.")
    seen: set[str] = set()
    deduped: list[str] = []
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    return deduped
