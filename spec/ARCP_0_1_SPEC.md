# ARCP 0.1 Specification

**Agent Runtime Compatibility Protocol, version 0.1**

## 1. Scope

ARCP defines a deterministic protocol for declaring and resolving compatibility
between three parties:

- **Harness** — the agent runtime that executes agents
- **Beta** — the workbench that renders runs and configures agents
- **Agent** — the code / configuration being run

Each party publishes a **compatibility document** (JSON). The **resolver**
compares these documents and produces a **resolution** (JSON) that is either
`allowed` or `blocked`, along with structured blockers and warnings.

## 2. Document kinds

Three kinds of compatibility documents exist:

| Kind      | Who publishes it | Purpose                                    |
|-----------|------------------|--------------------------------------------|
| `harness` | Runtime operator | Describes what the runtime provides        |
| `beta`    | Workbench team   | Describes what the workbench supports      |
| `agent`   | Agent author     | Describes what the agent requires          |

## 3. Schema versioning

Every document and resolution includes `arcp_schema_version`. For ARCP 0.1 the
value is `"0.1"`. Future versions will use `"0.2"`, `"0.3"`, etc.

Schema files live in `schemas/`:
- `compatibility_document_v0_1.schema.json`
- `compatibility_resolution_v0_1.schema.json`

## 4. Compatibility document fields

### All documents

| Field                | Type   | Required | Description                              |
|----------------------|--------|----------|------------------------------------------|
| `arcp_schema_version`| string | yes      | Must be `"0.1"`                          |
| `kind`               | string | yes      | `"harness"`, `"beta"`, or `"agent"`      |
| `id`                 | string | yes      | Unique identifier for the component      |
| `version`            | string | yes      | Semver version of the component          |
| `name`               | string | yes      | Human-readable name                      |
| `description`        | string | yes      | Human-readable description               |

### Harness-specific fields

| Field         | Type             | Description                                          |
|---------------|------------------|------------------------------------------------------|
| `contracts`   | dict[str, str]   | Contract name → version the runtime implements       |
| `tools`       | list[str]        | Tools the runtime exposes to agents                  |
| `capabilities`| list[str]        | Named capabilities the runtime provides              |
| `event_types` | list[str]        | Event types the runtime can emit                     |
| `constraints` | dict             | Operational constraints (network, secrets, review)   |

### Beta-specific fields

| Field         | Type             | Description                                          |
|---------------|------------------|------------------------------------------------------|
| `supports`    | dict[str, str]   | Version ranges of components this beta supports      |
| `contracts`   | list[str]        | Contract schemas this beta can render                |
| `tools`       | list[str]        | Tools the beta's UI supports                         |
| `capabilities`| list[str]        | Named capabilities the beta renders                  |
| `event_types` | list[str]        | Event types the beta can display                     |
| `constraints` | dict             | UI constraints (provider selection, etc.)            |

### Agent-specific fields

| Field                  | Type             | Description                                    |
|------------------------|------------------|------------------------------------------------|
| `requires`             | dict[str, str]   | Version ranges for harness and optionally beta |
| `contracts`            | dict[str, str]   | Contract versions the agent expects            |
| `tools`                | list[str]        | Tools the agent needs                          |
| `capabilities`         | list[str]        | Capabilities the agent needs                   |
| `event_types`          | list[str]        | Event types the agent consumes                 |
| `human_review_required`| bool             | Whether agent requires human review            |
| `memory_write`         | string           | Memory write policy (`"none"`, `"own"`, etc.)  |
| `external_network`     | string           | Network access policy (`"none"`, `"provider_only"`, etc.) |

## 5. Resolution output fields

| Field               | Type    | Description                                    |
|---------------------|---------|------------------------------------------------|
| `arcp_schema_version`| string | Always `"0.1"`                                 |
| `compatible`        | bool    | True if no blockers                            |
| `decision`          | string  | `"allowed"` or `"blocked"`                     |
| `resolved_versions` | dict    | The actual versions of harness, beta, agent    |
| `matched`           | dict    | Intersection of (agent requires) ∩ (harness provides) ∩ (beta supports) for tools, capabilities, and contracts. Items only appear if all three parties agree on them. |
| `warnings`          | list    | Non-blocking compatibility notes               |
| `blockers`          | list    | Blocking incompatibilities                     |
| `suggested_actions` | list    | (Only on blocked) Human-readable suggestions   |

### Decision model

| `compatible` | `decision`            | Meaning                                       |
|--------------|-----------------------|-----------------------------------------------|
| `true`       | `allowed`             | Agent can run. No blockers found.             |
| `true`       | `allowed` (warnings)  | Agent can run. Warnings MAY be non-empty;     |
|              |                       | they document non-fatal concerns but do NOT   |
|              |                       | prevent execution.                            |
| `false`      | `blocked`             | Agent cannot run. At least one blocker        |
|              |                       | exists and must be resolved.                  |

**Key principle:** `decision: allowed` does not guarantee an empty
`warnings` list. Warnings are informational and MUST NOT be treated as
blockers.

## 6. Resolver rules

### Blocker rules (any failure → `blocked`)

1. **Version mismatch (agent→harness)**: `agent.requires.harness` must be a
   semver range satisfied by `harness.version`.
2. **Version mismatch (agent→beta)**: If `agent.requires.beta` exists, it must
   be satisfied by `beta.version`.
3. **Beta supports harness**: `beta.supports.harness` must be satisfied by
   `harness.version`.
4. **Tools (harness)**: Every tool in `agent.tools` must appear in
   `harness.tools`.
5. **Tools (beta)**: Every tool in `agent.tools` must appear in `beta.tools`.
6. **Capabilities (harness)**: Every capability in `agent.capabilities` must
   appear in `harness.capabilities`.
7. **Capabilities (beta)**: Every capability in `agent.capabilities` must
   appear in `beta.capabilities`.
8. **Contracts**: Every contract in `agent.contracts` must be provided by
   `harness.contracts` with a matching version and supported by `beta.contracts`.
9. **Event types**: Every event type in `agent.event_types` must be emitted by
   `harness.event_types`.

### Warning rules (non-blocking)

1. **Un-rendered capability**: Harness provides a capability that Beta does not
   support.
2. **Un-displayable event type**: Beta cannot display agent event types (agent
   can still run).
3. **Provider selection disabled**: Agent uses provider-related capabilities but
   Beta has disabled provider selection.
4. **Broad version range**: Agent version range spans multiple major versions
   and should be narrowed.

## 7. Blocker types

| Type                           | Description                                  |
|--------------------------------|----------------------------------------------|
| `version_mismatch`             | Agent-required version range not satisfied   |
| `harness_unsupported_by_beta`  | Beta does not support this harness version   |
| `missing_tool`                 | Required tool not available                  |
| `missing_capability`           | Required capability not available            |
| `missing_contract`             | Required contract not present                |
| `contract_version_mismatch`    | Contract version doesn't match               |
| `missing_event_type`           | Required event type not emitted              |

## 8. Warning types

| Type                              | Description                                  |
|-----------------------------------|----------------------------------------------|
| `capability_not_rendered_by_beta` | Beta doesn't render a harness capability     |
| `event_type_not_renderable`       | Beta cannot display an event type            |
| `provider_selection_disabled`     | Beta provider selection is off               |
| `broad_version_range`             | Version range spans multiple major versions  |

## 9. Security constraints

Compatibility documents must not contain secrets (API keys, tokens, passwords).
The CLI's `validate` command performs a recursive check for field names matching
patterns such as `api_key`, `apikey`, `secret`, `token`, `password`, `bearer`,
and `authorization`.

## 10. Future extension points

- Custom constraints / policy rules
- Extended contract version negotiation
- Signed compatibility documents
- Plugin-contributed capability definitions
- Multi-harness / multi-beta resolution graphs
- Agent-defined optional features

---

**Note for Workbench Beta example files in this repo**: The ARCP 0.1 examples
use Beta that supports Harness `>=1.3.2,<1.4.0` because ARCP is defined before
the Harness 1.3.3 compatibility export API exists. Production Beta is expected
to use Harness 1.3.3+ once the compatibility export API is available.
