"""Tests for schema validation and secret detection."""

from __future__ import annotations

import json
import os

import pytest

from arcp.validation import (
    check_secrets,
    validate_document,
    validate_resolution,
)

_HERE = os.path.dirname(os.path.abspath(__file__))
_EXAMPLES = os.path.join(_HERE, "..", "examples")


@pytest.fixture
def harness_doc():
    with open(os.path.join(_EXAMPLES, "harness_1_3_2.compat.json")) as f:
        return json.load(f)


@pytest.fixture
def beta_doc():
    with open(os.path.join(_EXAMPLES, "workbench_beta_0_1.compat.json")) as f:
        return json.load(f)


@pytest.fixture
def agent_doc():
    with open(os.path.join(_EXAMPLES, "live_llm_reference_agent_0_1.compat.json")) as f:
        return json.load(f)


class TestValidateDocument:
    def test_valid_harness(self, harness_doc):
        assert validate_document(harness_doc) == []

    def test_valid_beta(self, beta_doc):
        assert validate_document(beta_doc) == []

    def test_valid_agent(self, agent_doc):
        assert validate_document(agent_doc) == []

    def test_missing_required_field(self):
        doc = {"arcp_schema_version": "0.1", "kind": "harness"}
        errors = validate_document(doc)
        assert len(errors) > 0

    def test_invalid_kind(self):
        doc = {
            "arcp_schema_version": "0.1",
            "kind": "unknown_kind",
            "id": "x",
            "version": "1.0",
            "name": "X",
            "description": "X",
        }
        errors = validate_document(doc)
        assert len(errors) > 0

    def test_invalid_schema_version(self):
        doc = {
            "arcp_schema_version": "0.2",
            "kind": "harness",
            "id": "x",
            "version": "1.0",
            "name": "X",
            "description": "X",
        }
        errors = validate_document(doc)
        assert len(errors) > 0

    def test_additional_properties_rejected(self):
        doc = {
            "arcp_schema_version": "0.1",
            "kind": "harness",
            "id": "x",
            "version": "1.0",
            "name": "X",
            "description": "X",
            "unknown_field": "should_not_be_here",
        }
        errors = validate_document(doc)
        assert len(errors) > 0


class TestValidateResolution:
    def test_valid_compatible_resolution(self):
        path = os.path.join(_EXAMPLES, "compatible_resolution.json")
        with open(path) as f:
            doc = json.load(f)
        assert validate_resolution(doc) == []

    def test_valid_incompatible_resolution(self):
        path = os.path.join(_EXAMPLES, "incompatible_resolution_missing_capability.json")
        with open(path) as f:
            doc = json.load(f)
        assert validate_resolution(doc) == []

    def test_resolution_requires_compatible(self):
        doc = {"arcp_schema_version": "0.1", "compatible": True}
        errors = validate_resolution(doc)
        assert len(errors) > 0


class TestCheckSecrets:
    def test_no_secrets(self, harness_doc):
        assert check_secrets(harness_doc) == []

    def test_no_secrets_beta(self, beta_doc):
        assert check_secrets(beta_doc) == []

    def test_no_secrets_agent(self, agent_doc):
        assert check_secrets(agent_doc) == []

    def test_detects_api_key(self):
        doc = {"kind": "harness", "api_key": "sk-1234"}
        findings = check_secrets(doc)
        assert len(findings) >= 1
        assert findings[0]["pattern"] in ("api_key", "apikey")

    def test_detects_secret(self):
        doc = {"kind": "harness", "credentials": {"secret": "s3cr3t"}}
        findings = check_secrets(doc)
        assert len(findings) >= 1

    def test_detects_token(self):
        doc = {"kind": "beta", "auth": {"bearer": "tok_xxx"}}
        findings = check_secrets(doc)
        assert len(findings) >= 1

    def test_detects_password(self):
        doc = {"kind": "agent", "database": {"password": "hunter2"}}
        findings = check_secrets(doc)
        assert len(findings) >= 1

    def test_detects_authorization(self):
        doc = {"kind": "harness", "headers": {"authorization": "Basic xxx"}}
        findings = check_secrets(doc)
        assert len(findings) >= 1
