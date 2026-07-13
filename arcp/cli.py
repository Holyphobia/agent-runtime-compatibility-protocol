"""ARCP CLI — validate, resolve, explain (v0.2)."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from arcp.resolver import resolve, resolve_environment
from arcp.validation import (
    check_secrets,
    upgrade_v0_1_to_v0_2,
    validate_document,
    validate_resolution,
)


def _load_json(path: str) -> dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def _load_optional_json(path: str) -> dict[str, Any] | None:
    if not path:
        return None
    return _load_json(path)


def cmd_validate(args: argparse.Namespace) -> int:
    doc = _load_json(args.input)
    errors = validate_document(doc)

    for e in errors:
        print(f"Validation error: {e}", file=sys.stderr)

    if not errors:
        ct = doc.get("component_type") or doc.get("kind", "unknown")
        ver = doc.get("component_version") or doc.get("version", "unknown")
        cid = doc.get("component_id") or doc.get("id", "?")
        print(f"Valid {ct} document {cid} v{ver}")

    secrets = check_secrets(doc)
    if secrets:
        for s in secrets:
            print(
                f"Warning: secret-like field '{s['field']}' (matched pattern: {s['pattern']})",
                file=sys.stderr,
            )

    # Upgrade notice for v0.1 docs
    if doc.get("arcp_schema_version") == "0.1":
        print("Note: Document uses v0.1 format. Consider upgrading to v0.2.", file=sys.stderr)

    return 1 if errors else 0


def cmd_resolve(args: argparse.Namespace) -> int:
    if args.environment:
        env = _load_json(args.environment)
        result = resolve_environment(env)
    else:
        harness = _load_json(args.harness)
        beta = _load_json(args.beta) if args.beta else {}
        agent = _load_json(args.agent)

        for name, doc in [("harness", harness), ("beta", beta), ("agent", agent)]:
            if doc:
                errs = validate_document(doc)
                if errs:
                    for e in errs:
                        print(f"{name}: {e}", file=sys.stderr)
                    return 1

        result = resolve(harness, beta, agent)

    if args.schema_validate:
        rerrs = validate_resolution(result)
        if rerrs:
            for e in rerrs:
                print(f"Resolution validation error: {e}", file=sys.stderr)
            return 1

    if args.format == "json":
        print(json.dumps(result, indent=2))
    elif args.format == "text":
        _print_text(result)

    # Exit code: 0 = allowed/warnings, 1 = blocked/denied/indeterminate
    decision = result.get("decision", "")
    if decision in ("denied", "indeterminate", "blocked"):
        return 1
    return 0


def cmd_explain(args: argparse.Namespace) -> int:
    resolution = _load_json(args.resolution)

    rerrs = validate_resolution(resolution)
    if rerrs:
        for e in rerrs:
            print(f"Resolution validation error: {e}", file=sys.stderr)
        return 1

    _print_text(resolution)
    return 0


def _print_text(resolution: dict[str, Any]) -> None:
    decision = resolution.get("decision", "unknown")
    compatible = resolution.get("compatible", False)
    versions = resolution.get("resolved_versions", {})
    matched_components = resolution.get("matched_components", [])
    matched_contracts = resolution.get("matched_contracts", {})
    matched_caps = resolution.get("matched_capabilities", [])
    missing_req_caps = resolution.get("missing_required_capabilities", [])
    missing_opt_caps = resolution.get("missing_optional_capabilities", [])
    unknown_caps = resolution.get("unknown_capabilities", [])
    blockers = resolution.get("blockers", [])
    warnings_list = resolution.get("warnings", [])
    reasons = resolution.get("reasons", [])
    remediation = resolution.get("remediation", [])

    print("ARCP Compatibility Resolution")
    print("=" * 40)
    print(f"  Compatible:  {compatible}")
    print(f"  Decision:    {decision}")
    print()

    if versions:
        print("Resolved Versions:")
        for k, v in versions.items():
            print(f"  {k}: {v}")
        print()

    print("Components:")
    for c in matched_components:
        print(f"  + {c}")
    print()

    if matched_caps:
        print(f"Matched Capabilities ({len(matched_caps)}):")
        for c in matched_caps:
            print(f"  + {c}")
        print()

    if matched_contracts:
        print("Matched Contracts:")
        for cname, cver in matched_contracts.items():
            print(f"  {cname}: {cver}")
        print()

    if missing_req_caps:
        print(f"Missing Required Capabilities ({len(missing_req_caps)}):")
        for c in missing_req_caps:
            print(f"  - {c}")
        print()

    if missing_opt_caps:
        print(f"Missing Optional Capabilities ({len(missing_opt_caps)}):")
        for c in missing_opt_caps:
            print(f"  ~ {c}")
        print()

    if unknown_caps:
        print(f"Unknown Capabilities ({len(unknown_caps)}):")
        for c in unknown_caps:
            print(f"  ? {c}")
        print()

    if warnings_list:
        print(f"Warnings ({len(warnings_list)}):")
        for w in warnings_list:
            print(f"  - {w}")
        print()

    if reasons:
        print(f"Reasons ({len(reasons)}):")
        for r in reasons:
            print(f"  - {r}")
        print()

    if blockers:
        print(f"Blockers ({len(blockers)}):")
        for b in blockers:
            _print_blocker(b)
        print()

    if remediation:
        print("Remediation:")
        for r in remediation:
            print(f"  - {r}")
        print()


def _print_blocker(b: dict[str, Any]) -> None:
    btype = b.get("type", "?")
    parts: list[str] = []
    for key in ("tool", "capability", "contract", "event_type", "field", "detail"):
        val = b.get(key)
        if val:
            parts.append(f"{key}={val}")
    detail = ", ".join(parts)
    print(f"  [{btype}] {detail}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ARCP v0.2 — Agent Runtime Compatibility Protocol CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # validate
    p_val = sub.add_parser("validate", help="Validate a compatibility document")
    p_val.add_argument("--input", required=True, help="Path to compat JSON file")
    p_val.set_defaults(func=cmd_validate)

    # resolve
    p_res = sub.add_parser("resolve", help="Resolve compatibility between components")
    p_res.add_argument("--harness", help="Harness compat JSON")
    p_res.add_argument("--beta", help="Beta compat JSON")
    p_res.add_argument("--agent", help="Agent compat JSON")
    p_res.add_argument(
        "--environment", "-e",
        help="Environment JSON file with multi-component definitions",
    )
    p_res.add_argument(
        "--format", choices=["json", "text"], default="text",
        help="Output format (default: text)",
    )
    p_res.add_argument(
        "--schema-validate", action="store_true",
        help="Also validate the resolution against the resolution schema",
    )
    p_res.set_defaults(func=cmd_resolve)

    # explain
    p_exp = sub.add_parser("explain", help="Explain a resolution result in text")
    p_exp.add_argument("--resolution", required=True, help="Resolution JSON file")
    p_exp.set_defaults(func=cmd_explain)

    parsed = parser.parse_args()
    sys.exit(parsed.func(parsed))
