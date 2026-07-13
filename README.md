# ARCP — Agent Runtime Compatibility Protocol

**Version 0.2**

ARCP is an open-source protocol and library that defines how agent runtimes,
workbenches, agents, tools, and LLM providers declare compatibility requirements,
and how a deterministic resolver decides whether a specific multi-component
combination is compatible.

## Why deterministic compatibility?

- **No LLM in the loop** — compatibility is decided by a static resolver, not an
  AI judge. Suitable for pre-flight checks, CI/CD gates, and audit trails.
- **Multi-component resolution** — v0.2 resolves environments with harness, beta,
  multiple agents, tool packs, and LLM providers in a single call.
- **Structured decisions** — four decision types (allowed, allowed_with_warnings,
  denied, indeterminate) with actionable remediation messages.
- **JSON in, JSON out** — every document and resolution is a plain JSON file.
  No database, no server, no network calls.

## What ARCP is not

ARCP validates compatibility. It does not:
- Invoke tools or call LLM providers
- Run agents or store secrets
- Replace Harness policy enforcement
- Replace MCP (tool transport)

## Document kinds (v0.2)

| Type                | Description                                      |
|---------------------|--------------------------------------------------|
| `harness`           | Agent runtime (tools, capabilities, contracts)   |
| `beta`              | Workbench/operator UI                            |
| `agent`             | Installable skill with requirements              |
| `tool`              | Single tool providing capabilities               |
| `tool_pack`         | Group of tools providing capabilities            |
| `llm_provider_profile` | LLM provider capabilities and constraints    |

## Install / dev setup

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/).

```bash
cd arcp
uv sync
uv run pytest -v
```

## CLI usage

### Validate a compatibility document

```bash
uv run arcp validate --input fixtures/harness_1_3_9.compat.json
```

### Resolve compatibility (component arguments)

```bash
uv run arcp resolve \
  --harness fixtures/harness_1_3_9.compat.json \
  --beta fixtures/beta_0_2_0.compat.json \
  --agent fixtures/ica_0_3_0.compat.json \
  --format json
```

### Resolve compatibility (environment file)

```bash
uv run arcp resolve --environment fixtures/env_future_interactive_stack.json --format json
```

### Explain a resolution

```bash
uv run arcp explain --resolution resolution.json
```

## Python API

```python
import arcp

# Load documents
harness = arcp.load_json_file("harness.compat.json")
beta    = arcp.load_json_file("beta.compat.json")
agent   = arcp.load_json_file("agent.compat.json")

# Resolve (3-party)
result = arcp.resolve(harness, beta, agent)

# Or resolve a full environment
result = arcp.resolve_environment({
    "harness": harness,
    "beta": beta,
    "agent": agent,
    "tools": [...],
    "provider": {...},
})

print(result["decision"])      # "allowed", "allowed_with_warnings", "denied", "indeterminate"
print(result["remediation"])   # actionable suggestions
```

## Decision model

| Compatible | Decision              | Meaning                                  |
|------------|-----------------------|------------------------------------------|
| True       | `allowed`             | All requirements satisfied               |
| True       | `allowed_with_warnings` | Mandatory requirements met, optional gaps |
| False      | `denied`              | Mandatory requirement fails              |
| False      | `indeterminate`       | Mandatory fact cannot be established     |

## Resolution structure (v0.2)

```json
{
  "arcp_schema_version": "0.2",
  "compatible": true,
  "decision": "allowed_with_warnings",
  "resolved_versions": { "harness": "1.3.9", "beta": "0.2.0", "agent": "0.3.0" },
  "matched_components": ["harness:agent-harness:1.3.9", "agent:ica:0.3.0"],
  "matched_contracts": { "agent_manifest": "1.1" },
  "matched_capabilities": ["llm.completion", "web.fetch"],
  "missing_required_capabilities": [],
  "missing_optional_capabilities": ["web.search"],
  "warnings": ["Optional capability web.search is not available."],
  "blockers": [],
  "reasons": [],
  "remediation": []
}
```

## v0.1 backward compatibility

Existing v0.1 documents are auto-detected and resolved using the legacy resolver.
The v0.1 output format (nested `matched.tools`, `matched.capabilities`, `matched.contracts`)
is preserved for backward compatibility. An upgrade notice is printed during validation.

## Secret detection

ARCP's `validate` command and `check_secrets()` function scan document field names
for secret-like patterns (`api_key`, `secret`, `token`, `password`, `authorization`, etc.).
Legitimate ARCP vocabulary terms (`secret_policy`, `secret_ref_only`) are allowed.

## Contract families

Agent manifest, run request, run result, interactive run control, run events,
artifacts, human review, checkpoint/resume, cancellation, input/output schema.

## Capability vocabulary

Namespaced canonical form: `llm.completion`, `web.fetch`, `web.search`, `web.crawl`,
`document.read`, `file.write`, `email.send`. Legacy `UPPER_CASE` identifiers
(`LLM_COMPLETION`, `WEB_FETCH`) are automatically normalized.

## Worked example

See the environment fixtures for a complete worked example resolving:
- Harness v1.3.9
- Beta v0.2.0
- Information Collector Agent v0.3.0
- Web Basic Tool Pack
- Hosted OpenAI-Compatible provider

```
uv run arcp resolve --environment fixtures/env_future_interactive_stack.json --format text
```

## License

Apache 2.0
