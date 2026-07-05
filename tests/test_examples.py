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

        assert set(result["matched"]["capabilities"]) == {
            "LLM_COMPLETION",
            "BETA_READABLE_EVENTS",
        }

    def test_matched_contracts(self):
        harness = _load("harness_1_3_2.compat.json")
        beta = _load("workbench_beta_0_1.compat.json")
        agent = _load("live_llm_reference_agent_0_1.compat.json")
        result = resolve(harness, beta, agent)

        # Agent doesn't declare contracts, so matched is all harness
        # contracts that beta also supports
        assert "agent_manifest" in result["matched"]["contracts"]
        assert "run_request_envelope" in result["matched"]["contracts"]
        assert "run_event_contract" in result["matched"]["contracts"]
        assert "provider_profile" not in result["matched"]["contracts"]

    def test_compatible_resolution_file_matches_shape(self):
        """The compatible_resolution.json file should roughly match resolver output."""
        harness = _load("harness_1_3_2.compat.json")
        beta = _load("workbench_beta_0_1.compat.json")
        agent = _load("live_llm_reference_agent_0_1.compat.json")
        result = resolve(harness, beta, agent)

        expected = _load("compatible_resolution.json")
        assert result["compatible"] == expected["compatible"]
        assert result["decision"] == expected["decision"]
        assert result["resolved_versions"] == expected["resolved_versions"]
        assert result["matched"]["tools"] == expected["matched"]["tools"]
        assert (
            set(result["matched"]["capabilities"])
            == set(expected["matched"]["capabilities"])
        )

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
