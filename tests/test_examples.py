"""Tests that verify example files are valid and produce expected resolution shapes."""

from __future__ import annotations

import json
import os

import pytest

from arcp.resolver import resolve
from arcp.validation import check_secrets, validate_document

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXAMPLES = os.path.join(_HERE, "..", "examples")


def _load(name: str) -> dict:
    with open(os.path.join(_EXAMPLES, name)) as f:
        return json.load(f)


class TestExamplesValidate:
    def test_harness_validates(self):
        doc = _load("harness_1_3_2.compat.json")
        assert validate_document(doc) == []
        assert check_secrets(doc) == []

    def test_beta_validates(self):
        doc = _load("workbench_beta_0_1.compat.json")
        assert validate_document(doc) == []
        assert check_secrets(doc) == []

    def test_agent_validates(self):
        doc = _load("live_llm_reference_agent_0_1.compat.json")
        assert validate_document(doc) == []
        assert check_secrets(doc) == []

    def test_compatible_resolution_validates(self):
        doc = _load("compatible_resolution.json")
        from arcp.validation import validate_resolution

        assert validate_resolution(doc) == []

    def test_incompatible_resolution_validates(self):
        doc = _load("incompatible_resolution_missing_capability.json")
        from arcp.validation import validate_resolution

        assert validate_resolution(doc) == []


class TestExampleResolution:
    def test_examples_resolve_as_compatible(self):
        harness = _load("harness_1_3_2.compat.json")
        beta = _load("workbench_beta_0_1.compat.json")
        agent = _load("live_llm_reference_agent_0_1.compat.json")
        result = resolve(harness, beta, agent)

        assert result["compatible"] is True
        assert result["decision"] == "allowed"
        assert result["blockers"] == []

    def test_matched_tools(self):
        harness = _load("harness_1_3_2.compat.json")
        beta = _load("workbench_beta_0_1.compat.json")
        agent = _load("live_llm_reference_agent_0_1.compat.json")
        result = resolve(harness, beta, agent)

        assert result["matched"]["tools"] == ["harness.llm.complete"]

    def test_matched_capabilities(self):
        harness = _load("harness_1_3_2.compat.json")
        beta = _load("workbench_beta_0_1.compat.json")
        agent = _load("live_llm_reference_agent_0_1.compat.json")
        result = resolve(harness, beta, agent)

        # Agent only declares LLM_COMPLETION and BETA_READABLE_EVENTS.
        # MANIFEST_PATH_RUN is in both harness and beta but agent does
        # not require it, so it is not in matched.
        assert result["matched"]["capabilities"] == [
            "BETA_READABLE_EVENTS",
            "LLM_COMPLETION",
        ]

    def test_matched_contracts(self):
        harness = _load("harness_1_3_2.compat.json")
        beta = _load("workbench_beta_0_1.compat.json")
        agent = _load("live_llm_reference_agent_0_1.compat.json")
        result = resolve(harness, beta, agent)

        assert "agent_manifest" in result["matched"]["contracts"]
        assert "run_request_envelope" in result["matched"]["contracts"]
        assert "run_event_contract" in result["matched"]["contracts"]
        assert "provider_profile" not in result["matched"]["contracts"]

    def test_no_manifest_path_run_warning(self):
        """Beta now supports MANIFEST_PATH_RUN -> no warning for it."""
        harness = _load("harness_1_3_2.compat.json")
        beta = _load("workbench_beta_0_1.compat.json")
        agent = _load("live_llm_reference_agent_0_1.compat.json")
        result = resolve(harness, beta, agent)

        cap_warnings = [
            w.get("capability") for w in result["warnings"]
            if w.get("type") == "capability_not_rendered_by_beta"
        ]
        assert "MANIFEST_PATH_RUN" not in cap_warnings

    def test_provider_profile_gateway_warning(self):
        """PROVIDER_PROFILE_GATEWAY is still not in beta -> warning remains."""
        harness = _load("harness_1_3_2.compat.json")
        beta = _load("workbench_beta_0_1.compat.json")
        agent = _load("live_llm_reference_agent_0_1.compat.json")
        result = resolve(harness, beta, agent)

        cap_warnings = [
            w.get("capability") for w in result["warnings"]
            if w.get("type") == "capability_not_rendered_by_beta"
        ]
        assert "PROVIDER_PROFILE_GATEWAY" in cap_warnings

    # ── drift-prevention: example file must exactly match resolver ─────

    def test_compatible_resolution_equals_resolver_output(self):
        """compatible_resolution.json must exactly match the deterministic resolver output
        for the three shipped example documents.

        This prevents drift between the example and the actual resolver behaviour.
        """
        harness = _load("harness_1_3_2.compat.json")
        beta = _load("workbench_beta_0_1.compat.json")
        agent = _load("live_llm_reference_agent_0_1.compat.json")
        result = resolve(harness, beta, agent)

        expected = _load("compatible_resolution.json")
        assert result == expected, (
            "compatible_resolution.json does not match resolver output.\n"
            f"Resolver:  {json.dumps(result, indent=2)}\n"
            f"Expected:  {json.dumps(expected, indent=2)}"
        )

    def test_cli_resolve_json_equals_example(self):
        """CLI --format json must produce output matching compatible_resolution.json."""
        import subprocess
        import sys

        _PROJECT = os.path.join(_HERE, "..")
        r = subprocess.run(
            ["uv", "run", "--directory", _PROJECT, "arcp", "resolve",
             "--harness", os.path.join(_EXAMPLES, "harness_1_3_2.compat.json"),
             "--beta", os.path.join(_EXAMPLES, "workbench_beta_0_1.compat.json"),
             "--agent", os.path.join(_EXAMPLES, "live_llm_reference_agent_0_1.compat.json"),
             "--format", "json"],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, r.stderr
        cli_output = json.loads(r.stdout)
        expected = _load("compatible_resolution.json")
        assert cli_output == expected, (
            "CLI resolve JSON output does not match compatible_resolution.json"
        )

    def test_manifest_path_run_declared_in_harness_and_beta(self):
        """MANIFEST_PATH_RUN must be present in both harness and beta capability
        declarations (since Beta relies on manifest-path execution)."""
        harness = _load("harness_1_3_2.compat.json")
        beta = _load("workbench_beta_0_1.compat.json")
        assert "MANIFEST_PATH_RUN" in harness.get("capabilities", [])
        assert "MANIFEST_PATH_RUN" in beta.get("capabilities", [])

    def test_manifest_path_run_not_in_matched_capabilities(self):
        """Even though MANIFEST_PATH_RUN is declared by both harness and beta,
        it must NOT appear in matched.capabilities because the reference
        agent does not require it."""
        harness = _load("harness_1_3_2.compat.json")
        beta = _load("workbench_beta_0_1.compat.json")
        agent = _load("live_llm_reference_agent_0_1.compat.json")
        result = resolve(harness, beta, agent)
        assert "MANIFEST_PATH_RUN" not in result["matched"]["capabilities"]

    def test_no_blockers_in_compatible_resolution(self):
        doc = _load("compatible_resolution.json")
        assert doc["compatible"] is True
        assert doc["decision"] == "allowed"
        assert doc["blockers"] == []

    def test_no_network_calls_in_imports(self):
        """Ensure arcp imports don't trigger network calls."""
        import arcp  # noqa: F811
        import arcp.models  # noqa: F811
        import arcp.semver  # noqa: F811
        import arcp.validation  # noqa: F811
        import arcp.resolver  # noqa: F811
        import arcp.cli  # noqa: F811


class TestIncompatibleExample:
    def test_incompatible_shape(self):
        doc = _load("incompatible_resolution_missing_capability.json")
        assert doc["compatible"] is False
        assert doc["decision"] == "blocked"
        assert len(doc["blockers"]) > 0
        assert "suggested_actions" in doc
        assert len(doc["suggested_actions"]) > 0
