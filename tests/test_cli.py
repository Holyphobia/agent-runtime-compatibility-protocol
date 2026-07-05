"""Tests for the ARCP CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXAMPLES = os.path.join(_HERE, "..", "examples")
_PROJECT = os.path.join(_HERE, "..")


def _arcp(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "--directory", _PROJECT, "arcp", *args],
        capture_output=True,
        text=True,
    )


class TestCLIValidate:
    def test_validate_harness(self):
        path = os.path.join(_EXAMPLES, "harness_1_3_2.compat.json")
        r = _arcp("validate", "--input", path)
        assert r.returncode == 0, r.stderr

    def test_validate_beta(self):
        path = os.path.join(_EXAMPLES, "workbench_beta_0_1.compat.json")
        r = _arcp("validate", "--input", path)
        assert r.returncode == 0, r.stderr

    def test_validate_agent(self):
        path = os.path.join(_EXAMPLES, "live_llm_reference_agent_0_1.compat.json")
        r = _arcp("validate", "--input", path)
        assert r.returncode == 0, r.stderr

    def test_validate_invalid_file(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text('{"kind": "harness"}')
        r = _arcp("validate", "--input", str(bad))
        assert r.returncode != 0

    def test_validate_secret_detected(self, tmp_path):
        """Fields like api_key are rejected by schema validation (additionalProperties)."""
        path = tmp_path / "secret.json"
        path.write_text(
            json.dumps(
                {
                    "arcp_schema_version": "0.1",
                    "kind": "harness",
                    "id": "x",
                    "version": "1.0",
                    "name": "X",
                    "description": "X",
                    "api_key": "sk-xxx",
                }
            )
        )
        r = _arcp("validate", "--input", str(path))
        assert r.returncode != 0
        assert "api_key" in r.stderr or "not allowed" in r.stderr


class TestCLIResolve:
    def test_resolve_json(self):
        r = _arcp(
            "resolve",
            "--harness",
            os.path.join(_EXAMPLES, "harness_1_3_2.compat.json"),
            "--beta",
            os.path.join(_EXAMPLES, "workbench_beta_0_1.compat.json"),
            "--agent",
            os.path.join(_EXAMPLES, "live_llm_reference_agent_0_1.compat.json"),
            "--format",
            "json",
        )
        assert r.returncode == 0, r.stderr
        result = json.loads(r.stdout)
        assert result["compatible"] is True
        assert result["decision"] == "allowed"

    def test_resolve_text(self):
        r = _arcp(
            "resolve",
            "--harness",
            os.path.join(_EXAMPLES, "harness_1_3_2.compat.json"),
            "--beta",
            os.path.join(_EXAMPLES, "workbench_beta_0_1.compat.json"),
            "--agent",
            os.path.join(_EXAMPLES, "live_llm_reference_agent_0_1.compat.json"),
            "--format",
            "text",
        )
        assert r.returncode == 0, r.stderr

    def test_resolve_incompatible(self, tmp_path):
        """Modify agent to require an unsupported capability."""
        agent_path = os.path.join(_EXAMPLES, "live_llm_reference_agent_0_1.compat.json")
        with open(agent_path) as f:
            agent = json.load(f)
        agent["capabilities"].append("READ_EXTERNAL")
        bad_agent = tmp_path / "bad_agent.json"
        with open(bad_agent, "w") as f:
            json.dump(agent, f)

        r = _arcp(
            "resolve",
            "--harness",
            os.path.join(_EXAMPLES, "harness_1_3_2.compat.json"),
            "--beta",
            os.path.join(_EXAMPLES, "workbench_beta_0_1.compat.json"),
            "--agent",
            str(bad_agent),
            "--format",
            "json",
        )
        assert r.returncode != 0
        result = json.loads(r.stdout)
        assert result["compatible"] is False
        assert result["decision"] == "blocked"


class TestCLIExplain:
    def test_explain_compatible(self):
        path = os.path.join(_EXAMPLES, "compatible_resolution.json")
        r = _arcp("explain", "--resolution", path)
        assert r.returncode == 0, r.stderr
        assert "Compatible:" in r.stdout

    def test_explain_incompatible(self):
        path = os.path.join(_EXAMPLES, "incompatible_resolution_missing_capability.json")
        r = _arcp("explain", "--resolution", path)
        assert r.returncode == 0, r.stderr
        assert "Blockers" in r.stdout

    def test_explain_invalid_input(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{}")
        r = _arcp("explain", "--resolution", str(bad))
        assert r.returncode != 0
