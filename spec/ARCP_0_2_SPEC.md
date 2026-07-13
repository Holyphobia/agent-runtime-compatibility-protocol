# ARCP 0.2 Specification

**Agent Runtime Compatibility Protocol, version 0.2**

## 1. Scope

ARCP defines a deterministic protocol for declaring and resolving compatibility
between components in an agent runtime environment. v0.2 extends the v0.1
three-party model to support multi-component environments with six component
types:

| Component type         | Description                                    |
|------------------------|------------------------------------------------|
| `harness`              | Agent runtime (tools, capabilities, contracts) |
| `beta`                 | Workbench / operator UI                       |
| `agent`                | Installable skill with requirements            |
| `tool`                 | Single tool providing capabilities             |
| `tool_pack`            | Group of tools providing capabilities          |
| `llm_provider_profile` | LLM provider capabilities and constraints      |

Each component publishes a **compatibility document** (JSON). The **resolver**
compares these documents and produces a **resolution** (JSON) with one of four
decisions: `allowed`, `allowed_with_warnings`, `denied`, or `indeterminate`.

## 2. Deterministic design

ARCP is explicitly **not** an LLM-based judge. Compatibility is decided by a
static resolver with these properties:

- **No LLM in the loop** — suitable for pre-flight checks, CI/CD gates, and
  audit trails.
- **Multi-component resolution** — resolves environments with harness, beta,
  multiple agents, tool packs, and LLM providers in a single call.
- **Structured decisions** — four decision types with actionable remediation
  messages.
- **JSON in, JSON out** — every document and resolution is a plain JSON file.
  No database, no server, no network calls.
- **Deterministic** — the same inputs always produce the same output.

## 3. What ARCP does not do

- Invoke tools or call LLM providers
- Run agents or store secrets
- Replace Harness policy enforcement (security, permissions, billing)
- Replace MCP (tool transport protocol)
- Evaluate agent trustworthiness or authorization
- Check live provider endpoint availability

## 4. Schema versioning

Every document and resolution includes `arcp_schema_version`. v0.2 documents
use `"0.2"`. v0.1 documents use `"0.1"` and are auto-detected by the resolver.

Schema files live in `schemas/`:
- `compatibility_document_v0_2.schema.json`
- `compatibility_resolution_v0_2.schema.json`
- `compatibility_document_v0_1.schema.json` (legacy)
- `compatibility_resolution_v0_1.schema.json` (legacy)

## 5. Compatibility document format (v0.2)

### Common fields (all component types)

| Field                 | Type   | Required | Description                            |
|-----------------------|--------|----------|----------------------------------------|
| `arcp_schema_version` | string | yes      | Must be `"0.2"`                        |
| `component_type`      | string | yes      | One of the six component types         |
| `component_id`        | string | yes      | Unique identifier                      |
| `component_version`   | string | yes      | Semver version                         |
| `protocol_version`    | string | yes      | Must be `"0.2"`                        |
| `name`                | string | no       | Human-readable name                    |
| `description`         | string | no       | Human-readable description             |

### Fields by component type

#### Harness

| Field                      | Type             | Description                                      |
|----------------------------|------------------|--------------------------------------------------|
| `contracts`                | dict[str, str]   | Contract name → version the runtime implements   |
| `capabilities.provides`    | list[str]        | Named capabilities the runtime provides          |
| `tools`                    | list[str]        | Tools the runtime exposes to agents              |
| `events.supported_types`   | list[str]        | Event types the runtime emits                    |
| `checkpoint_resume`        | dict             | Checkpoint/resume capabilities                   |
| `cancellation`             | dict             | Cancellation support details                     |
| `human_review`             | dict             | Human review support details                     |

#### Beta

| Field                      | Type             | Description                                      |
|----------------------------|------------------|--------------------------------------------------|
| `supports.harness`         | string           | Semver range of supported harness versions       |
| `contracts`                | dict[str, str]   | Contract schemas the beta can render             |
| `capabilities.provides`    | list[str]        | Named capabilities the beta renders              |
| `tools`                    | list[str]        | Tools the beta UI supports                       |
| `events`                   | dict             | Event display capabilities                       |
| `artifacts`                | dict             | Artifact rendering support                       |
| `human_review`             | dict             | Review UI capabilities                           |
| `checkpoint_resume`        | dict             | Resume support                                   |
| `cancellation`             | dict             | Cancellation UI support                          |

#### Agent

| Field                      | Type             | Description                                      |
|----------------------------|------------------|--------------------------------------------------|
| `requires.harness`         | string           | Semver range of required harness version         |
| `requires.beta`            | string           | Semver range of required beta version (optional) |
| `contracts`                | dict[str, str]   | Contract versions the agent expects              |
| `capabilities.required`    | list[str]        | Capabilities the agent requires                  |
| `capabilities.optional`    | list[str]        | Capabilities the agent can use if available      |
| `tools`                    | list[str]        | Tools the agent needs                            |
| `llm_requirements`         | dict             | LLM provider requirements (see section 6)        |
| `artifacts`                | dict             | Artifact schema requirements                     |
| `human_review`             | dict             | Review schema requirements                       |
| `checkpoint_resume`        | dict             | Checkpoint schema requirements                   |
| `events`                   | dict             | Event type consumption                           |
| `incompatibilities`        | list[str]        | Declared incompatibilities (always blocking)     |

#### Tool / Tool Pack

| Field                      | Type             | Description                                      |
|----------------------------|------------------|--------------------------------------------------|
| `capabilities.provides`    | list[str]        | Capabilities this tool/pack provides             |
| `tools`                    | list[str]        | Tool identifiers this pack contains              |

#### LLM Provider Profile

| Field                      | Type             | Description                                      |
|----------------------------|------------------|--------------------------------------------------|
| `provider.capabilities`    | list[str]        | LLM capabilities (`llm.completion`, etc.)        |
| `provider.supports_structured_output` | bool  | Whether structured output is supported           |
| `provider.supports_tool_calling`      | bool  | Whether tool calling is supported                |
| `provider.context_window`  | integer          | Maximum context window size                      |

## 6. LLM requirements (agent field)

Agents declare LLM provider requirements under `llm_requirements`:

| Field                        | Type    | Description                                |
|------------------------------|---------|--------------------------------------------|
| `capabilities`               | list    | Required LLM capabilities                  |
| `minimum_context_window`     | integer | Minimum context window in tokens           |
| `structured_output_required` | bool    | Whether structured output is required      |
| `tool_calling_required`      | bool    | Whether tool calling is required           |
| `streaming_optional`         | bool    | Whether streaming is acceptable but not required |
| `quality_tier`               | string  | Minimum quality tier requirement           |

Provider capabilities are resolved in Stage 5 of the resolver against the
selected `llm_provider_profile`. Missing required LLM capabilities produce
blockers; unknown capabilities (not in canonical vocabulary) may produce
`indeterminate` decisions.

## 7. Contract families

v0.2 defines a fixed set of recognized contract families:

| Contract family              | Description                                    |
|------------------------------|------------------------------------------------|
| `agent_manifest`             | Agent identity, description, and metadata      |
| `run_request`                | Request structure to start a run               |
| `run_result`                 | Result structure from a completed run          |
| `interactive_run_control`    | Interactive session control (pause/resume)     |
| `run_events`                 | Event stream during a run                      |
| `artifacts`                  | Artifact lifecycle and rendering               |
| `human_review`               | Human-in-the-loop review workflow              |
| `checkpoint_resume`          | Checkpoint creation and resume                 |
| `cancellation`               | Cooperative run cancellation                   |
| `input_schema`               | Structured input schema for agents             |
| `output_schema`              | Structured output schema for agents            |

Contract versions are specified as semver ranges (e.g., `"1.0"`, `">=1.1,<2.0"`).
Unknown contract families declared by an agent produce blockers.

## 8. Capability vocabulary

Capabilities use lowercase dotted notation. v0.2 defines these canonical
capabilities:

| Canonical            | Legacy form      | Description                       |
|----------------------|------------------|-----------------------------------|
| `llm.completion`     | `LLM_COMPLETION` | LLM text completion               |
| `web.fetch`          | `WEB_FETCH`      | Fetch web content                 |
| `web.search`         | `WEB_SEARCH`     | Search the web                    |
| `web.crawl`          | `SITE_CRAWL`     | Crawl websites                    |
| `document.read`      | `DOCUMENT_READ`  | Read documents                    |
| `file.write`         | `FILE_WRITE`     | Write files                       |
| `email.send`         | `EMAIL_SEND`     | Send email                        |
| `structured_output`  | —                | Structured output support         |

### Normalization rules

1. Legacy `UPPER_CASE` identifiers are mapped to canonical form via an
   alias table (e.g., `LLM_COMPLETION` → `llm.completion`).
2. Unknown capabilities (not in canonical set) pass through as-is for
   forward compatibility but may contribute to `indeterminate` decisions.
3. Capabilities are compared in normalized form during resolution.

## 9. Resolution output format

### v0.2 resolution

```json
{
  "arcp_schema_version": "0.2",
  "compatible": true,
  "decision": "allowed_with_warnings",
  "resolved_versions": {
    "harness": "1.3.9",
    "beta": "0.2.0",
    "agent": "0.3.0"
  },
  "matched_components": [
    "harness:agent-harness:1.3.9",
    "beta:workbench_beta:0.2.0",
    "agent:information_collector_agent:0.3.0"
  ],
  "matched_contracts": {
    "agent_manifest": "1.1"
  },
  "matched_capabilities": ["llm.completion", "web.fetch"],
  "missing_required_capabilities": [],
  "missing_optional_capabilities": ["web.search"],
  "incompatible_contracts": [],
  "unknown_capabilities": [],
  "warnings": ["Optional capability web.search is not available."],
  "blockers": [],
  "reasons": [],
  "remediation": []
}
```

| Field                           | Type             | Description                                 |
|---------------------------------|------------------|---------------------------------------------|
| `arcp_schema_version`           | string           | Always `"0.2"`                              |
| `compatible`                    | bool             | True if no blockers                         |
| `decision`                      | string           | One of four decision types                  |
| `resolved_versions`             | dict             | Versions of all matched components          |
| `matched_components`            | list[str]        | Component identity strings                  |
| `matched_contracts`             | dict[str, str]   | Contracts matched between agent and harness |
| `matched_capabilities`          | list[str]        | Required capabilities that are provided     |
| `missing_required_capabilities` | list[str]        | Required capabilities not found             |
| `missing_optional_capabilities` | list[str]        | Optional capabilities not found             |
| `incompatible_contracts`        | list             | Contracts with version mismatches           |
| `unknown_capabilities`          | list[str]        | Capabilities not in canonical vocabulary    |
| `warnings`                      | list[str]        | Non-blocking compatibility notes            |
| `blockers`                      | list[dict]       | Blocking incompatibilities                  |
| `reasons`                       | list[str]        | Structured reasons for decisions            |
| `remediation`                   | list[str]        | Actionable suggestions to resolve issues    |

### v0.1 backward-compatible resolution

When the resolver detects v0.1 documents, it produces the v0.1 output format
preserving the nested `matched` object (with `tools`, `capabilities`,
`contracts` sub-keys), `"blocked"` decision string, and `suggested_actions`
list.

## 10. Decision model

| Compatible | Decision                | Meaning                                    |
|------------|-------------------------|--------------------------------------------|
| `true`     | `allowed`               | All mandatory requirements satisfied       |
| `true`     | `allowed_with_warnings` | Mandatory requirements met, optional gaps  |
| `false`    | `denied`                | Mandatory requirement fails                |
| `false`    | `indeterminate`         | Mandatory fact cannot be established       |

- **`allowed`**: No blockers and no warnings. All requirements are satisfied.
- **`allowed_with_warnings`**: Agent can run but optional capabilities are
  missing or beta rendering gaps exist. Warnings are informational and MUST NOT
  prevent execution.
- **`denied`**: At least one blocker exists (version mismatch, missing
  capability, missing tool, missing contract, etc.). The agent cannot run.
- **`indeterminate`**: A mandatory requirement's status cannot be determined
  (e.g., provider capability status is unknown). The agent cannot run but the
  failure mode differs from a definite `denied`.

## 11. Resolver stages

The v0.2 resolver processes compatibility in seven stages:

### Stage 1: Validate document structure
- Check harness and agent are present
- Validate contract family names (unknown families → blocker)

### Stage 2: Component identity
- Build `matched_components` list from all component IDs and versions

### Stage 3: Version and contract resolution
- **Harness version requirement**: agent `requires.harness` range vs harness
  version (blocker on mismatch)
- **Beta version requirement**: agent `requires.beta` range vs beta version
  (blocker on mismatch)
- **Agent contracts**: each agent contract must exist in harness with matching
  version (blocker on mismatch). Missing beta contracts produce warnings, not
  blockers.
- **Beta supports harness**: beta `supports.harness` range vs harness version
  (blocker on mismatch)

### Stage 4: Capability resolution
- Collect capabilities provided by harness, beta, tools, and tool packs
- For each agent: check required capabilities against all provided sources
- Optional capabilities missing → warning
- Required capabilities missing → blocker
- Unknown capabilities (not in canonical vocabulary) → tracked for
  indeterminate decision

### Stage 5: Provider / LLM requirements
- Check LLM capabilities against provider profile
- Structured output requirement vs provider capability
- Tool calling requirement vs provider capability
- Context window minimum vs provider capacity
- Unknown provider capabilities → indeterminate
- No provider selected when agent has LLM requirements → warning

### Stage 6: Beta rendering / control support
- Event type display coverage (warning on gap, generic fallback)
- Artifact schema version matching (warning on mismatch)
- Human review schema version matching (warning on mismatch)
- Renderer hint support (warning with generic fallback note)

### Stage 7: Explicit incompatibilities
- Agent-declared `incompatibilities` list → always blockers

### Final decision
- Any blockers → `denied` or `indeterminate` (depending on reason type)
- Only warnings → `allowed_with_warnings`
- Clean → `allowed`
- Duplicate remediation messages are deduplicated

## 12. Resolution methods

The resolver supports two calling conventions:

### Three-party (legacy-style)

```python
result = arcp.resolve(harness_doc, beta_doc, agent_doc)
```

### Environment dict

```python
result = arcp.resolve_environment({
    "harness": harness_doc,
    "beta": beta_doc,
    "agent": agent_doc,
    "tools": [tool_doc, ...],
    "tool_packs": [pack_doc, ...],
    "provider": provider_doc,
})
```

The environment dict is automatically normalized: singular `agent` is wrapped
into a list, `providers` is unwrapped to `provider` (uses first if list).
v0.1 detection runs on the normalized environment.

## 13. Semantic version matching

Versions are parsed as tuples of integers: `"1.3.9"` → `(1, 3, 9)`.
Pre-release and build metadata suffixes are stripped before comparison.

Range format: comma-separated constraints (e.g., `">=1.3,<2.0"`). Each
constraint is an operator (`>=`, `<=`, `>`, `<`, `==`) followed by a version.
Constraints are combined with AND logic.

Broad ranges (spanning multiple major versions) trigger a warning in the
legacy v0.1 resolver.

## 14. Secret detection

The `validate` command and `check_secrets()` function scan document field names
for secret-like patterns:

**Denylist patterns**: `api_key`, `apikey`, `access_key`, `secret_key`,
`client_secret`, `access_token`, `refresh_token`, `bearer_token`,
`authorization`, `password`, `passwd`, `credential`, `private_key`, standalone
`secret`, standalone `token`.

**Allowlist** (terms that match patterns but are legitimate ARCP vocabulary):
`secret_policy`, `secret_ref`, `secret_ref_only`, `provider` and related
provider field names.

## 15. Backward compatibility with v0.1

v0.1 documents are auto-detected by the presence of `arcp_schema_version: "0.1"`
or a `kind` field. The resolver routes them to the legacy resolver which:

- Preserves the v0.1 nested `matched` output format
- Uses `"blocked"` (not `"denied"`) decision strings
- Returns `suggested_actions` (not `remediation`)
- Validates against v0.1 JSON schemas
- Supports the `upgrade_v0_1_to_v0_2()` function for migration

Detection logic: all non-None documents must be v0.1 for legacy routing.
Mixed v0.1/v0.2 environments are not supported.

## 16. Blocker types

| Type                           | Description                                 |
|--------------------------------|---------------------------------------------|
| `version_mismatch`             | Agent-required version range not satisfied  |
| `harness_unsupported_by_beta`  | Beta does not support this harness version  |
| `missing_tool`                 | Required tool not available                 |
| `missing_capability`           | Required capability not available           |
| `missing_contract`             | Required contract not present               |
| `contract_version_mismatch`    | Contract version doesn't match              |
| `missing_event_type`           | Required event type not emitted             |
| `provider_missing_capability`  | Provider lacks required LLM capability      |
| `provider_lacks_capability`    | Provider lacks structured output/tool calls |
| `unknown_contract_family`      | Agent uses unrecognized contract family     |
| `explicit_incompatibility`     | Agent-declared incompatibility              |
| `missing_component`            | Required component (harness/agent) missing  |

## 17. CLI reference

### Validate a compatibility document

```bash
uv run arcp validate --input <file.json>
```

Exit code: 0 on valid, 1 on invalid. Prints validation errors and secret
detection warnings to stdout.

### Resolve compatibility (component files)

```bash
uv run arcp resolve \
  --harness <file.json> \
  --beta <file.json> \
  --agent <file.json> \
  --format json|text
```

### Resolve compatibility (environment file)

```bash
uv run arcp resolve \
  --environment <file.json> \
  --format json|text
```

### Explain a resolution

```bash
uv run arcp explain --resolution <file.json>
```

### Exit codes

| Decision                        | Exit code |
|---------------------------------|-----------|
| `allowed` / `allowed_with_warnings` | 0     |
| `denied` / `indeterminate` / `blocked` | 1 |

## 18. Python API

| Function / Constant                              | Purpose                                     |
|--------------------------------------------------|---------------------------------------------|
| `arcp.resolve(harness, beta, agent, ...)`        | Deterministic compatibility resolution      |
| `arcp.resolve_environment(environment)`           | Environment-dict convenience wrapper        |
| `arcp.validate_compatibility_document(doc)`       | JSON Schema validation of a compat document |
| `arcp.validate_resolution_document(doc)`          | JSON Schema validation of a resolution      |
| `arcp.check_secrets(doc)`                         | Recursive secret-like field detection       |
| `arcp.load_json_file(path)`                       | Load a JSON file from disk                  |
| `arcp.upgrade_v0_1_to_v0_2(doc)`                  | Convert v0.1 document to v0.2 format        |
| `arcp.ARCP_SCHEMA_VERSION`                        | Current schema version constant (`"0.2"`)   |

```python
import arcp

harness = arcp.load_json_file("harness.compat.json")
beta    = arcp.load_json_file("beta.compat.json")
agent   = arcp.load_json_file("agent.compat.json")

result = arcp.resolve(harness, beta, agent)

if result["compatible"]:
    print(f"Compatible: {result['decision']}")
else:
    print(f"Incompatible: {result['decision']}")
    for b in result["blockers"]:
        print(f"  - {b.get('detail', b['type'])}")
```

## 19. Environment fixtures

The repository includes environment fixture files demonstrating common
scenarios:

| Fixture                                    | Scenario                              |
|--------------------------------------------|---------------------------------------|
| `env_current_stack.json`                   | Current production stack, all matching|
| `env_future_interactive_stack.json`        | Future stack with full interactive     |
| `env_missing_required_tool.json`           | Agent needs tool not in environment    |
| `env_unsupported_contract.json`            | Agent demands contract not available   |
| `env_indeterminate_provider.json`          | Provider with unknown capabilities     |

## 20. Security constraints

- Compatibility documents must not contain secrets (API keys, tokens,
  passwords).
- The `validate` command and `check_secrets()` scan for denylisted field names.
- Legitimate ARCP vocabulary terms are allowlisted to prevent false positives.
- The resolver is offline and deterministic — no network calls occur during
  resolution.

---

**Version history**: v0.1 (3-party, 2 decision types) → v0.2 (6 component types,
4 decision types, capability normalization, provider resolution).
See the [migration guide](ARCP_0_1_TO_0_2_MIGRATION.md) for upgrade details.
