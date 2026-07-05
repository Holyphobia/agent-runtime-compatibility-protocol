# ARCP 0.1 Integration Guide

This guide explains how **Agent Harness 1.3.3+** and **Workbench Beta 0.1**
should use ARCP for compatibility checking.

No integration code is implemented in this repo. This document is a
specification for downstream consumers.

---

## 1. How Harness 1.3.3 should export an ARCP harness document

When an agent is submitted for execution, the Harness must be able to
produce a **harness compatibility document** that reflects its current
runtime state.

Minimal approach — hardcoded constants:

```python
import arcp

def build_harness_compat_doc():
    return {
        "arcp_schema_version": "0.1",
        "kind": "harness",
        "id": "agent-harness",
        "version": "1.3.3",
        "name": "Agent Harness",
        "description": "Auto-generated compatibility document",
        "contracts": {
            "agent_manifest": "0.1",
            "run_request_envelope": "0.1",
            "provider_profile": "0.1",
            "run_event_contract": "0.1",
        },
        "tools": ["harness.llm.complete"],
        "capabilities": [
            "LLM_COMPLETION",
            "MANIFEST_PATH_RUN",
            "BETA_READABLE_EVENTS",
            "PROVIDER_PROFILE_GATEWAY",
        ],
        "event_types": [
            "run.requested", "agent.manifest_loaded",
            "compatibility.checked", "policy.checked",
            "run.started", "llm.completion_requested",
            "llm.completion_allowed", "llm.completion_completed",
            "run.completed", "run.failed", "run.blocked",
        ],
        "constraints": {
            "default_network": "deny_by_default",
            "secret_policy": "secret_ref_only",
            "human_review_supported": True,
        },
    }
```

The document MUST be produced **before** any agent code executes, so that
compatibility is checked at the gate, not during a run.

---

## 2. How Harness 1.3.3 should check an agent document

```python
import arcp

def check_agent_compatibility(agent_doc_path: str) -> bool:
    harness_doc = build_harness_compat_doc()
    beta_doc = load_beta_compat_doc()      # see section 3
    agent_doc = arcp.load_json_file(agent_doc_path)

    # Validate all three documents
    for label, doc in [("harness", harness_doc),
                       ("beta", beta_doc),
                       ("agent", agent_doc)]:
        errs = arcp.validate_compatibility_document(doc)
        if errs:
            raise ValueError(f"{label} document invalid: {errs}")

    # Resolve compatibility
    result = arcp.resolve(harness_doc, beta_doc, agent_doc)

    if result["decision"] == "blocked":
        for b in result["blockers"]:
            log.error("Blocked: %s", b)
        return False

    # Warnings are informational — execution may proceed
    for w in result.get("warnings", []):
        log.info("Warning: %s", w.get("detail", ""))

    return True
```

**CLI equivalent** (e.g. for a CI pipeline):

```bash
arcp resolve \
  --harness harness.compat.json \
  --beta beta.compat.json \
  --agent agent.compat.json \
  --format json
```

---

## 3. How Workbench Beta 0.1 should load documents

The Beta should load three documents before starting a run:

1. **Its own beta document** — statically defined or generated from Beta
   capabilities.
2. **The Harness compatibility document** — fetched or read from the
   Harness instance the Beta connects to.
3. **The Agent compatibility document** — shipped with the agent
   distribution (e.g. at `/opt/agents/<agent>/arcp.compat.json`).

```python
import arcp

def smoke_check(harness_path, beta_path, agent_path):
    h = arcp.load_json_file(harness_path)
    b = arcp.load_json_file(beta_path)
    a = arcp.load_json_file(agent_path)

    # Validate documents
    assert arcp.validate_compatibility_document(h) == []
    assert arcp.validate_compatibility_document(b) == []
    assert arcp.validate_compatibility_document(a) == []

    # Resolve
    result = arcp.resolve(h, b, a)

    # Show human-readable output
    for w in result.get("warnings", []):
        print(f"  ⚠ {w['detail']}")
    for b in result.get("blockers", []):
        print(f"  ✗ {b['type']}: {b}")

    return result["compatible"]
```

---

## 4. CLI commands for smoke-testing

```bash
# Validate a single document
arcp validate --input examples/harness_1_3_2.compat.json

# Resolve compatibility (JSON output for programmatic consumption)
arcp resolve \
  --harness examples/harness_1_3_2.compat.json \
  --beta examples/workbench_beta_0_1.compat.json \
  --agent examples/live_llm_reference_agent_0_1.compat.json \
  --format json

# Explain a saved resolution in human-readable text
arcp explain --resolution examples/compatible_resolution.json
```

---

## 5. Python API functions

| Function / Constant                         | Purpose                                      |
|---------------------------------------------|----------------------------------------------|
| `arcp.resolve(harness, beta, agent)`        | Deterministic compatibility resolution       |
| `arcp.validate_compatibility_document(doc)` | JSON Schema validation of a compat document  |
| `arcp.validate_resolution_document(doc)`    | JSON Schema validation of a resolution       |
| `arcp.check_secrets(doc)`                   | Recursive secret-like field detection        |
| `arcp.load_json_file(path)`                 | Load a JSON file from disk                   |
| `arcp.ARCP_SCHEMA_VERSION`                  | Current schema version constant (`"0.1"`)    |

Import from the top-level package:

```python
import arcp
result = arcp.resolve(harness, beta, agent)
```

Internal modules (`arcp.resolver`, `arcp.validation`, `arcp.semver`, `arcp.cli`)
are implementation details and may change between minor versions.

---

## 6. Decision model

| `compatible` | `decision`            | Meaning                                       |
|--------------|-----------------------|-----------------------------------------------|
| `true`       | `allowed`             | Agent can run. No blockers found.             |
| `true`       | `allowed` (warnings)  | Agent can run, but some concerns exist        |
|              |                       | (e.g. Beta cannot render a capability, or a   |
|              |                       | version range is broad). Warnings are not     |
|              |                       | blockers — they do not prevent execution.     |
| `false`      | `blocked`             | Agent cannot run. At least one blocker was    |
|              |                       | found (version mismatch, missing tool,        |
|              |                       | missing capability, missing contract, etc.).  |

Key distinction: **blockers prevent execution; warnings do not.**

---

## 7. What ARCP explicitly does not decide

- **Security approval** — ARCP does not evaluate whether an agent is
  trustworthy, authenticated, or authorised to run.
- **Runtime permissioning** — ARCP does not grant or deny filesystem,
  network, or secret access. Those decisions happen later in the Harness
  policy engine.
- **Pricing / billing** — ARCP does not meter, bill, or enforce quotas.
- **Install entitlement** — ARCP does not check whether the agent is
  licensed for the current Harness or Beta deployment.
- **Live provider availability** — ARCP resolves static capability
  compatibility, not whether a specific LLM provider endpoint is reachable
  or has quota.
- **Remote code execution** — ARCP does not move, fetch, or run code.
- **Network calls** — The resolver is intentionally offline/deterministic.
  No HTTP, gRPC, or IPC calls are made during resolution.
