"""Tests that the public Python API surface is stable and importable."""

from __future__ import annotations

import tempfile

import pytest


class TestPublicApiImports:
    """Verify that the top-level ``arcp`` package exports the expected API."""

    def test_import_package(self):
        import arcp

        assert hasattr(arcp, "resolve")
        assert hasattr(arcp, "validate_compatibility_document")
        assert hasattr(arcp, "validate_resolution_document")
        assert hasattr(arcp, "check_secrets")
        assert hasattr(arcp, "load_json_file")
        assert hasattr(arcp, "ARCP_SCHEMA_VERSION")

    def test_schema_version_constant(self):
        import arcp

        assert arcp.ARCP_SCHEMA_VERSION == "0.2"

    def test_load_json_file(self):
        import arcp

        import json

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"test_key": True}, f)
            fname = f.name

        doc = arcp.load_json_file(fname)
        assert doc == {"test_key": True}

    def test_validate_compatibility_document(self):
        import arcp

        doc = {
            "arcp_schema_version": "0.1",
            "kind": "harness",
            "id": "test",
            "version": "1.0.0",
            "name": "Test",
            "description": "Test harness",
        }
        errors = arcp.validate_compatibility_document(doc)
        assert errors == []

    def test_validate_invalid_document(self):
        import arcp

        doc = {"kind": "harness"}
        errors = arcp.validate_compatibility_document(doc)
        assert len(errors) > 0

    def test_validate_resolution_document(self):
        import arcp

        doc = {
            "arcp_schema_version": "0.1",
            "compatible": True,
            "decision": "allowed",
            "resolved_versions": {"harness": "1.0", "beta": "0.1", "agent": "0.1"},
            "matched": {"tools": [], "capabilities": [], "contracts": {}},
            "warnings": [],
            "blockers": [],
        }
        errors = arcp.validate_resolution_document(doc)
        assert errors == []

    def test_check_secrets(self):
        import arcp

        doc = {"kind": "harness", "api_key": "sk-xxx"}
        findings = arcp.check_secrets(doc)
        assert len(findings) >= 1

    def test_resolve_from_api(self):
        """End-to-end smoke test using the public resolve() function."""
        import arcp

        import json
        import os

        _HERE = os.path.dirname(os.path.abspath(__file__))
        examples = os.path.join(_HERE, "..", "examples")

        harness = arcp.load_json_file(os.path.join(examples, "harness_1_3_2.compat.json"))
        beta = arcp.load_json_file(os.path.join(examples, "workbench_beta_0_1.compat.json"))
        agent = arcp.load_json_file(
            os.path.join(examples, "live_llm_reference_agent_0_1.compat.json")
        )

        result = arcp.resolve(harness, beta, agent)
        assert result["compatible"] is True
        assert result["decision"] == "allowed"
        assert result["blockers"] == []
