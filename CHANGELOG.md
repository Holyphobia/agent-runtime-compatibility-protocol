# Changelog

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
