# ARCP v0.1 → v0.2 Migration Guide

This guide explains how to migrate compatibility documents and consumers from
ARCP v0.1 to v0.2.

## Quick summary

| Area               | v0.1                            | v0.2                              |
|--------------------|----------------------------------|-----------------------------------|
| Component types    | 3 (harness, beta, agent)        | 6 (+ tool, tool_pack, provider)   |
| Decision types     | 2 (allowed, blocked)            | 4 (allowed, allowed_with_warnings, denied, indeterminate) |
| Capability format  | `UPPER_CASE`                    | `dotted.canonical` (auto-normalized) |
| Document schema    | `kind`/`id`/`version` top-level | `component_type`/`component_id`/`component_version`/`protocol_version` |
| Capability field   | Flat `capabilities: [...]`      | `capabilities: {provides, required, optional}` |
| Resolution output  | Nested `matched` object         | Flat fields with `matched_capabilities`, `blockers`, `remediation` |
| Output decision    | `"blocked"`                     | `"denied"` or `"indeterminate"`   |
| Beta contracts     | List `["contract_name", ...]`   | Dict `{"contract_name": "version", ...}` |
| Tool resolution    | Only harness/beta/agent         | Abstract: tools and tool_packs provide capabilities |

## Backward compatibility

v0.2 is fully backward compatible with v0.1 documents:

1. **Auto-detection**: v0.1 documents are recognized by
   `arcp_schema_version: "0.1"` or presence of a `kind` field, and are routed
   to the legacy resolver automatically.

2. **Legacy output format**: v0.1 documents produce v0.1-format resolutions
   (nested `matched`, `"blocked"` decision string, `suggested_actions`).

3. **Mixed environments**: A v0.2 resolver can process v0.1 documents with no
   code changes to the caller.

4. **Upgrade utility**: The `arcp.upgrade_v0_1_to_v0_2()` function converts
   v0.1 documents to v0.2 format.

## Breaking changes

### 1. Capability identifiers

**Change**: Capabilities are now lowercase dotted identifiers.

| v0.1              | v0.2               |
|-------------------|---------------------|
| `LLM_COMPLETION`  | `llm.completion`    |
| `WEB_FETCH`       | `web.fetch`         |
| `WEB_SEARCH`      | `web.search`        |

**Migration**: Update your documents to use canonical names, or keep using
`UPPER_CASE` — the resolver auto-normalizes them. New documents should use
canonical form.

### 2. Capability field structure

**Change**: The flat `capabilities: [...]` list is replaced with a structured
object.

**v0.1 (harness/beta)**:
```json
{
  "capabilities": ["LLM_COMPLETION", "WEB_FETCH"]
}
```

**v0.2 (harness/beta)**:
```json
{
  "capabilities": {
    "provides": ["llm.completion", "web.fetch"]
  }
}
```

**v0.2 (agent)**:
```json
{
  "capabilities": {
    "required": ["llm.completion"],
    "optional": ["web.search"]
  }
}
```

**Migration**: Restructure the `capabilities` field according to component
type. Harness/beta use `provides`; agents use `required` and `optional`.

### 3. Document identity fields

**Change**: v0.2 uses consistent naming across all component types.

| v0.1              | v0.2                |
|-------------------|----------------------|
| `"kind"`          | `"component_type"`   |
| `"id"`            | `"component_id"`     |
| `"version"`       | `"component_version"`|
| *(new)*           | `"protocol_version"` |

**Migration**: Add `protocol_version: "0.2"` and rename the identity fields.
The v0.1 fields (`kind`, `id`, `version`) are still accepted in v0.1 documents
but not in v0.2 documents.

### 4. Beta contracts format

**Change**: v0.1 beta uses a list of contract names; v0.2 uses a dict with
versions.

**v0.1**:
```json
{
  "contracts": ["agent_manifest", "run_request"]
}
```

**v0.2**:
```json
{
  "contracts": {
    "agent_manifest": "1.0",
    "run_request": "1.0"
  }
}
```

**Migration**: Convert beta contract lists to dicts with version numbers.

### 5. Decision types

**Change**: v0.2 splits `"blocked"` into `"denied"` and `"indeterminate"`, and
adds `"allowed_with_warnings"` as a distinct decision.

| v0.1       | v0.2                          |
|------------|--------------------------------|
| `allowed`  | `allowed` or `allowed_with_warnings` |
| `blocked`  | `denied` or `indeterminate`    |

**Migration**: Update decision-handling code. Treat `denied` and
`indeterminate` as equivalent to `blocked` (both mean incompatible). Treat
`allowed_with_warnings` the same as `allowed` (both mean compatible).

### 6. Resolution output structure

**Change**: v0.2 flattens the nested `matched` object.

**v0.1**:
```json
{
  "matched": {
    "tools": ["harness.llm.complete"],
    "capabilities": ["LLM_COMPLETION"],
    "contracts": {"agent_manifest": "0.1"}
  },
  "suggested_actions": [...]
}
```

**v0.2**:
```json
{
  "matched_capabilities": ["llm.completion"],
  "matched_contracts": {"agent_manifest": "1.1"},
  "remediation": [...]
}
```

**Migration**: Read from `matched_capabilities` instead of
`matched.capabilities`. Use `remediation` instead of `suggested_actions`.

### 7. Missing beta contracts

**Change**: v0.1 treats missing beta contracts as blockers. v0.2 treats them
as warnings (generic fallback assumed).

**Migration**: If you relied on beta contract blocking as a guard, add explicit
checks in your caller code.

## New features

### Tools and tool packs

v0.2 introduces abstract tool resolution. Tools and tool packs are standalone
component types that declare capabilities. This means capabilities can be
provided by tools rather than solely by the harness.

Example tool pack document:

```json
{
  "arcp_schema_version": "0.2",
  "component_type": "tool_pack",
  "component_id": "web-basic",
  "component_version": "1.0.0",
  "protocol_version": "0.2",
  "capabilities": {
    "provides": ["web.fetch", "web.search"]
  },
  "tools": ["web.fetch", "web.search"]
}
```

### LLM provider profiles

Providers are now a first-class component type. Agents declare LLM requirements
and the resolver checks them against the selected provider profile.

### Optional capabilities

Agents can declare `capabilities.optional` — missing optional capabilities
produce warnings, not blockers.

### Four decision types

The expanded decision model gives callers more information about the nature of
incompatibilities.

### Structured remediation

Instead of `suggested_actions`, v0.2 returns `remediation` — deduplicated,
actionable messages generated from blocker details.

## Step-by-step migration

### Step 1: Upgrade your documents

Run the upgrade utility on each v0.1 document:

```python
import arcp

v0_1_doc = arcp.load_json_file("old_doc.compat.json")
v0_2_doc = arcp.upgrade_v0_1_to_v0_2(v0_1_doc)
```

Or update documents manually following the field mapping in section 2 above.

### Step 2: Add new required fields

Ensure all v0.2 documents have:
- `protocol_version: "0.2"`
- `component_type` (one of the six types)
- `component_id`
- `component_version`

### Step 3: Restructure capabilities

Convert `capabilities: [...]` to `capabilities: {"provides": [...]}` for
harness/beta/tools. For agents, use `required` and `optional` sub-keys.

### Step 4: Update resolution consumers

If you read resolution output:
- Check `matched_capabilities` instead of `matched["capabilities"]`
- Handle four decision types instead of two (treat `denied`/`indeterminate` as
  "not compatible", `allowed_with_warnings` as "compatible")
- Use `remediation` list instead of `suggested_actions`
- Use `blockers` list (different structure from v0.1)

### Step 5: Add provider profiles (optional)

If using LLM provider resolution, create provider profile documents and add
`llm_requirements` to agent documents.

## Testing your migration

Validate all documents after migration:

```bash
uv run arcp validate --input my_document.compat.json
```

Resolve a full environment:

```bash
uv run arcp resolve --environment my_environment.json --format text
```

Check for v0.1 upgrade notices (printed to stderr):
```bash
uv run arcp validate --input old_v0_1_document.compat.json 2>&1
```
