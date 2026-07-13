# Changelog

## v0.2.1 (2026-07-13)

### Bug Fixes

- **Transitional Harness v1.3.9 export validation**: Documents with v0.1 structure
  (`kind`/`id`/`version`) but `arcp_schema_version: "0.2"` are now auto-detected
  as transitional, normalized to native v0.2 format, and pass validation and
  resolution without error.
- **Mandatory Beta contract enforcement**: Agent-declared contracts are now
  required from *both* harness and beta. Missing beta contracts produce blockers
  (`missing_contract`, `supported_by_beta: False`) instead of warnings, resulting
  in `denied` decisions when Beta is genuinely incompatible.
- **Missing optional capabilities produce `allowed_with_warnings`**: Even when
  no other warnings exist, missing optional capabilities now consistently cause
  `allowed_with_warnings` instead of silently producing `allowed`.
- **Duplicate component identity rejection**: Duplicate `component_type:component_id`
  pairs across any component type now produce a `duplicate_identity` blocker.

### Behavioral Changes

- Beta contract gaps that were previously warnings are now blockers (denial).
  This affects ICA 0.3.0 on Beta 0.1.3: previously `allowed_with_warnings`,
  now correctly `denied` (Beta 0.1.3 lacks interactive contracts).
- Missing optional capabilities with no other warnings: previously `allowed`,
  now `allowed_with_warnings`.

### Testing

- 3 tests updated to reflect new Beta contract denial behavior.
- 175 total tests passing.
- 30 scenario matrix checks all passing.

## v0.2.0 (2026-07-13)

### Features

- **Multi-component resolution**: Support for 6 component types — harness, beta,
  agent, tool, tool_pack, and llm_provider_profile — resolved in a single call.
- **Four decision types**: `allowed`, `allowed_with_warnings`, `denied`, and
  `indeterminate` replace the v0.1 two-decision model.
- **Capability normalization**: Legacy `UPPER_CASE` identifiers are automatically
  normalized to lowercase dotted notation (`LLM_COMPLETION` → `llm.completion`).
- **Structured capability fields**: Harness/beta use `capabilities.provides`;
  agents use `capabilities.required` and `capabilities.optional`.
- **LLM provider resolution**: Provider profiles with structured output, tool
  calling, and context window checks against agent `llm_requirements`.
- **Abstract tool resolution**: Tools and tool packs are standalone documents
  contributing capabilities, not tied to vendor-specific harness tools.
- **Contract family validation**: 11 recognized contract families with unknown
  family detection.
- **Beta support as warnings**: Missing beta contracts produce warnings
  (generic fallback assumed) instead of blockers.
- **Staged resolver**: 7-stage pipeline (validate → identity → contracts →
  capabilities → provider → beta → finalize).
- **Environment resolution**: Single JSON file contains all components for
  batch resolution via `--environment`.
- **Structured remediation**: Deduplicated, actionable remediation messages
  replacing v0.1 `suggested_actions`.

### Backward compatibility

- v0.1 documents are auto-detected and routed to the legacy resolver.
- v0.1 output format (nested `matched`, `"blocked"` decision) is preserved.
- `upgrade_v0_1_to_v0_2()` utility function for document migration.

### Documentation

- Full v0.2 protocol specification (`spec/ARCP_0_2_SPEC.md`).
- Migration guide from v0.1 to v0.2 (`spec/ARCP_0_1_TO_0_2_MIGRATION.md`).
- Updated README with v0.2 API examples and CLI reference.

### Testing

- 86 new v0.2-specific tests across 16 test classes.
- 89 existing v0.1 tests preserved and passing (175 total).
- Fixtures for 6 component types, 5 environment scenarios, and edge cases
  (secret detection, malformed documents, indeterminate provider).

## v0.1.0 (2026-06-30)

### Features

- Three-party resolution (harness, beta, agent).
- Two decision model: `allowed` or `blocked`.
- Semver version range matching.
- Contract, tool, and capability matching.
- Event type coverage checking.
- JSON Schema validation for documents and resolutions.
- Secret detection via field name denylist.

### Documentation

- v0.1 protocol specification (`spec/ARCP_0_1_SPEC.md`).
- Integration guide for downstream consumers (`spec/ARCP_0_1_INTEGRATION_GUIDE.md`).
