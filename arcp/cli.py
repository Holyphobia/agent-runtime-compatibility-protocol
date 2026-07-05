"""ARCP CLI — validate, resolve, explain."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from arcp.resolver import resolve
from arcp.validation import (
    check_secrets,
    validate_document,
    validate_resolution,
)


def _load_json(path: str) -> dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def cmd_validate(args: argparse.Namespace) -> int:
    doc = _load_json(args.input)
    errors = validate_document(doc)

    if errors:
        for e in errors:
            print(f"Validation error: {e}", file=sys.stderr)
        return 1

    secrets = check_secrets(doc)
    if secrets:
        for s in secrets:
            print(
                f"Warning: secret-like field '{s['field']}' (matched pattern: {s['pattern']})",
                file=sys.stderr,
            )

    kind = doc.get("kind", "unknown")
    version = doc.get("version", "unknown")
    print(f"Valid {kind} document {doc.get('id', '?')} v{version}")
    if secrets:
        print(f"  Secret-like fields detected: {len(secrets)}", file=sys.stderr)
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    harness = _load_json(args.harness)
    beta = _load_json(args.beta)
    agent = _load_json(args.agent)

    for name, doc in [("harness", harness), ("beta", beta), ("agent", agent)]:
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

    return 0 if result.get("compatible") else 1


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
    compatible = resolution.get("compatible", False)
    decision = resolution.get("decision", "unknown")
    versions = resolution.get("resolved_versions", {})
    matched = resolution.get("matched", {})
    blockers = resolution.get("blockers", [])
    warnings = resolution.get("warnings", [])
    suggestions = resolution.get("suggested_actions", [])

    print("ARCP Compatibility Resolution")
    print("=" * 40)
    print(f"  Compatible:  {compatible}")
    print(f"  Decision:    {decision}")
    print()
    print("Resolved Versions:")
    for k, v in versions.items():
        print(f"  {k}: {v}")
    print()

    print("Matched:")
    print(f"  Tools:       {', '.join(matched.get('tools', [])) or '(none)'}")
    print(f"  Capabilities: {', '.join(matched.get('capabilities', [])) or '(none)'}")
    contracts = matched.get("contracts", {})
    if contracts:
        print("  Contracts:")
        for cname, cver in contracts.items():
            print(f"    {cname}: {cver}")
    else:
        print("  Contracts:   (none)")
    print()

    if warnings:
        print(f"Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"  - [{w.get('type', '?')}] {w.get('detail', '')}")
        print()

    if blockers:
        print(f"Blockers ({len(blockers)}):")
        for b in blockers:
            _print_blocker(b)
        print()

    if suggestions:
        print("Suggested actions:")
        for s in suggestions:
            print(f"  - {s}")
        print()


def _print_blocker(b: dict[str, Any]) -> None:
    btype = b.get("type", "?")
    detail_parts: list[str] = []
    if "tool" in b:
        detail_parts.append(f"tool={b['tool']}")
    if "capability" in b:
        detail_parts.append(f"capability={b['capability']}")
    if "contract" in b:
        detail_parts.append(f"contract={b['contract']}")
    if "event_type" in b:
        detail_parts.append(f"event_type={b['event_type']}")
    if "expected" in b:
        detail_parts.append(f"expected={b['expected']}")
    if "actual" in b:
        detail_parts.append(f"actual={b['actual']}")
    detail = ", ".join(detail_parts)
    print(f"  - {btype}" + (f" ({detail})" if detail else ""))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ARCP — Agent Runtime Compatibility Protocol CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # validate
    p_val = sub.add_parser("validate", help="Validate a compatibility document")
    p_val.add_argument("--input", required=True, help="Path to compat JSON file")
    p_val.set_defaults(func=cmd_validate)

    # resolve
    p_res = sub.add_parser("resolve", help="Resolve compatibility between documents")
    p_res.add_argument("--harness", required=True, help="Harness compat JSON")
    p_res.add_argument("--beta", required=True, help="Beta compat JSON")
    p_res.add_argument("--agent", required=True, help="Agent compat JSON")
    p_res.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format (default: text)",
    )
    p_res.add_argument(
        "--schema-validate",
        action="store_true",
        help="Also validate the resolution against the resolution schema",
    )
    p_res.set_defaults(func=cmd_resolve)

    # explain
    p_exp = sub.add_parser("explain", help="Explain a resolution result in text")
    p_exp.add_argument("--resolution", required=True, help="Resolution JSON file")
    p_exp.set_defaults(func=cmd_explain)

    parsed = parser.parse_args()
    sys.exit(parsed.func(parsed))
