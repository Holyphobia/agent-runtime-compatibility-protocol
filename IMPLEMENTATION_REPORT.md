# ARCP v0.2.1 Implementation Report

## Meta

| Field             | Value                                    |
|-------------------|------------------------------------------|
| Package version   | `0.2.1`                                  |
| Protocol version  | `0.2`                                    |
| Status            | **READY**                                |

## v0.2.1 Changes

### 1. Transitional Harness v1.3.9 export support

The real Harness v1.3.9 `compatibility export` command produces documents with
v0.1 structure (`kind`/`id`/`version`) but declares `arcp_schema_version: "0.2"`.
These documents previously failed validation because the v0.1 schema rejects
`arcp_schema_version: "0.2"`, and the v0.2 schema requires `component_type`.

**Fix**: Added `is_transitional_document()` detection and
`normalize_transitional_document()` conversion in `arcp/models.py` and
`arcp/validation.py`. The resolver calls `_normalize_transitional_env()` during
initialization to convert any transitional documents to native v0.2 format
before resolution proceeds.

Transitional recognition is narrowly scoped:
- `arcp_schema_version` is `"0.2"`
- `kind` is present (no `component_type`)
- Legacy identity fields present (`id`, `version`)
- Expected compatibility sections present (`contracts` and/or `tools`)

### 2. Mandatory Beta contract enforcement

Previously, agent-declared contracts missing from Beta produced only warnings.
This was inconsistent with the v0.2 spec, which requires both harness and Beta
to support all agent-declared contracts.

**Fix**: `_resolve_agent_contracts()` in `arcp/resolver.py` now produces
blockers with `type: "missing_contract"` and `supported_by_beta: False` when
Beta lacks contracts the agent requires. This results in `denied` decisions.

Scenarios affected:
- ICA 0.3.0 on Beta 0.1.3 → now `denied` (was `allowed_with_warnings`)
- Beta lacks actionable review → now `denied` (was `allowed_with_warnings`)

### 3. Missing optional capabilities → `allowed_with_warnings`

Missing optional capabilities were correctly generating warnings but the
final decision was `allowed` when no other warnings existed. The v0.2 spec
requires missing optional capabilities to produce `allowed_with_warnings`.

**Fix**: `_finalize()` condition widened to `elif warnings_list or
result.get("missing_optional_capabilities"):` with a guard to populate
missing optional cap warnings into the warnings list before the decision is
made.

### 4. Duplicate component identity detection

The resolver previously tolerated duplicate component identities (e.g., two
agents with the same `component_type:component_id`). This could mask
configuration errors.

**Fix**: Added `_check_duplicate_identities()` function called in Stage 1
of the resolver. Uses identity key `component_type:component_id`. Duplicates
across any component type produce a `duplicate_identity` blocker.

## Scenario results (updated for v0.2.1)

### B — Interactive agent on current Beta (ICA 0.3.0 on Beta 0.1.3)
```
Decision: denied
Compatible: False
Blockers: missing_contract (5 contracts: interactive_run_control, artifacts,
          human_review, checkpoint_resume, cancellation)
```
Beta 0.1.3 lacks contracts that ICA 0.3.0 requires. Now correctly denied.

### E — Missing optional crawler
```
Decision: allowed_with_warnings
Compatible: True
Blockers: none
Warnings: 1 (optional web.crawl not available)
```
Previously `allowed`, now correctly `allowed_with_warnings`.

### G — Beta renderer fallback
```
Decision: denied
Compatible: False
Blockers: missing_contract (Beta 0.1.3 lacks 5 required contracts)
Warnings: renderer fallback notes (not reached due to contract denial)
```
Contract check fires before renderer check, producing correct denial.

## Fixtures

No new fixtures added. The transitional Harness export is tested using inline
documents in the scenario matrix.

## Tests

| Metric | Value |
|--------|-------|
| Full suite | 175 passed |
| Failed | 0 |
| Scenarios | 30/30 passed |

## Files changed for v0.2.1

| File | Change |
|------|--------|
| `arcp/models.py` | Added `is_transitional_document()`, `is_transitional_document()` public predicate |
| `arcp/validation.py` | Added `normalize_transitional_document()`, `is_transitional_format()`, updated `_detect_schema_version()` and `validate_document()` |
| `arcp/resolver.py` | Added 4 fixes: transitional normalization, beta contract blockers, optional cap warnings, duplicate identity check |
| `arcp/__init__.py` | Exported `normalize_transitional_document`, `is_transitional_format` |
| `pyproject.toml` | Version 0.2.1 |
| `tests/test_v0_2.py` | 3 tests updated for beta contract denial |
| `CHANGELOG.md` | v0.2.1 entry added |

## Meta

| Field             | Value                                    |
|-------------------|------------------------------------------|
| Branch            | `develop/0.2.0-plug-and-play-contracts`  |
| Starting commit   | `401b886` feat: implement ARCP 0.1 protocol baseline |
| Final commit      | *(to be created)*                        |
| Package version   | `0.2.0`                                  |
| Protocol version  | `0.2`                                    |
| Status            | **READY**                                |

## Protocol model

### Supported component types (6)

| # | Type                | Location                     |
|---|---------------------|------------------------------|
| 1 | `harness`           | `arcp/models.py:14`         |
| 2 | `beta`              | `arcp/models.py:14`         |
| 3 | `agent`             | `arcp/models.py:14`         |
| 4 | `tool`              | `arcp/models.py:14`         |
| 5 | `tool_pack`         | `arcp/models.py:14`         |
| 6 | `llm_provider_profile` | `arcp/models.py:14`      |

### Supported contract families (11)

`agent_manifest`, `run_request`, `run_result`, `interactive_run_control`, `run_events`, `artifacts`, `human_review`, `checkpoint_resume`, `cancellation`, `input_schema`, `output_schema`

Defined in `arcp/models.py:43`.

### Capability vocabulary (8 canonical)

| Canonical | Legacy alias | Description |
|-----------|-------------|-------------|
| `llm.completion` | `LLM_COMPLETION` | LLM text completion |
| `web.fetch` | `WEB_FETCH` | Fetch web content |
| `web.search` | `WEB_SEARCH` | Search the web |
| `web.crawl` | `SITE_CRAWL` | Crawl websites |
| `document.read` | `DOCUMENT_READ` | Read documents |
| `file.write` | `FILE_WRITE` | Write files |
| `email.send` | `EMAIL_SEND` | Send email |
| `structured_output` | — | Structured output support |

**Normalization**: `LLM_COMPLETION` and `llm.completion` both normalize to `llm.completion`. Legacy `UPPER_CASE` forms are mapped through an alias table in `arcp/models.py:72`. Unknown capabilities pass through as-is for forward compatibility but may contribute to `indeterminate` decisions.

### Version normalization

Implementation in `arcp/semver.py`.

- `parse_version("1.0")` → `(1, 0)`, `parse_version("1.0.0")` → `(1, 0, 0)` — padded to same length (`(1, 0, 0)`) during comparison via `_pad()`.
- `match_range(">=1.0,<2.0", "1.0.1")` → `True`
- `match_range("<2.0", "2.0.0")` → `False`
- Pre-release stripped: `"1.0.0-alpha"` → `(1, 0, 0)` — treated as `1.0.0`
- Build metadata stripped: `"1.0.0+build123"` → `(1, 0, 0)`
- Invalid version → `()` (empty tuple) → all range checks return `False`
- Broad range detection: `">=1.0,<3.0"` spans majors → `True` (warning in v0.1)

## Resolution

### Environment graph

Multi-component environment resolution supporting:
- 1 harness (required)
- 1 beta (optional)
- 1+ agents (required, at least 1)
- 0+ tools (optional)
- 0+ tool_packs (optional)
- 1 provider (optional)

Implementation: `arcp/resolver.py`. Entry points: `resolve()` (line 37), `resolve_environment()` (line 72).

### Resolver stages (7)

1. **Validate document structure** — required components, contract family names
2. **Component identity** — `matched_components` list
3. **Version/contract resolution** — harness/beta version ranges, contract matching
4. **Capability resolution** — required/optional, tool-provided, normalization
5. **Provider/LLM requirements** — capabilities, structured output, tool calling, context window
6. **Beta support** — events, artifacts, review, renderer hints (warnings)
7. **Finalize** — decision from blockers/warnings/unknowns

### Decision types (4)

| Decision | Compatible | Meaning | Trigger |
|----------|-----------|---------|---------|
| `allowed` | `true` | All requirements satisfied | No blockers, no warnings |
| `allowed_with_warnings` | `true` | Mandatory met, optional gaps | Warnings only, no blockers |
| `denied` | `false` | Mandatory requirement fails | Definite blocker(s) |
| `indeterminate` | `false` | Mandatory fact cannot be established | Unknown provider capability or unknown required capability |

### Decision precedence

1. Warning CANNOT override a blocker (blocker always wins)
2. Unknown mandatory capabilities upgrade to `indeterminate` (NOT `allowed`)
3. Unknown provider capabilities upgrade `denied` → `indeterminate`

### Required capability behavior

- Missing required capability → `blocker` → `denied`
- Unknown required capability (not in canonical vocabulary) → tracked → may contribute to `indeterminate`

### Optional capability behavior

- Missing optional capability → `warning` → `allowed_with_warnings`
- Never produces a blocker

### Provider resolution

- LLM capabilities checked against `provider.capabilities` list
- `structured_output_required` vs `supports_structured_output` (null → indeterminate)
- `tool_calling_required` vs `supports_tool_calling` (null → indeterminate)
- `minimum_context_window` vs `context_window` (insufficient → warning)
- No provider with agent LLM requirements → warning

### Beta support resolution

- Missing contracts → warnings (generic fallback assumed)
- Event type display gaps → warnings
- Artifact/review schema version mismatches → warnings
- Renderer hint gaps → warnings (with or without generic fallback note)

## Backward compatibility

### v0.1 behavior

- Auto-detected by `arcp_schema_version: "0.1"` or presence of `kind` field
- Routed to legacy resolver producing v0.1 output format
- Nested `matched` object (`tools`, `capabilities`, `contracts`)
- `"blocked"` decision string (not `"denied"`)
- `suggested_actions` list (not `remediation`)
- Pure v0.1 environments only (mixed v0.1/v0.2 uses v0.2 resolver)

### Migration behavior

- `upgrade_v0_1_to_v0_2(doc)` converts v0.1 format to v0.2
- CLI prints "upgrading" notice on stderr for v0.1 documents
- v0.1 JSON schemas preserved in `schemas/`

## CLI

### Validate

```
arcp validate --input <file>
```

Exit 0 on valid, 1 on invalid. Prints validation errors and secret detection warnings.

### Resolve

```
arcp resolve --harness <file> --beta <file> --agent <file> [--format json|text]
arcp resolve --environment <file> [--format json|text]
```

Exit 0 for allowed/warnings, 1 for denied/indeterminate/blocked.

### Explain

```
arcp explain --resolution <file>
```

Human-readable text output of a saved resolution.

### JSON output

Deterministic and machine-readable. Structure matches the resolution document format in `schemas/compatibility_resolution_v0_2.schema.json`.

## Fixtures

| Type | Files |
|------|-------|
| Harness | `harness_1_3_9.compat.json`, `harness_1_3_2_v0_1.compat.json`, `old_harness_no_checkpoint.compat.json` |
| Beta | `beta_0_1_3.compat.json`, `beta_0_2_0.compat.json`, `beta_no_actionable_review.compat.json` |
| Agents | `ica_0_2_0.compat.json`, `ica_0_3_0.compat.json` |
| Tools | `web_basic_tool_pack.compat.json`, `web_fetch_only_tool.compat.json` |
| Providers | `provider_hosted_openai.compat.json`, `provider_local_openai.compat.json`, `provider_no_structured_output.compat.json`, `provider_unknown_capabilities.compat.json`, `provider_profile_only_web.compat.json` |
| Environments | `env_current_stack.json`, `env_future_interactive_stack.json`, `env_missing_required_tool.json`, `env_unsupported_contract.json`, `env_indeterminate_provider.json` |
| Security | `secret_doc.compat.json` |

## Scenario results

### A — Current stack (Harness 1.3.9, Beta 0.1.3, ICA 0.2.0)
```
Decision: allowed
Compatible: True
Blockers: none
Warnings: none
```

### B — Interactive agent on current Beta (ICA 0.3.0 on Beta 0.1.3)
```
Decision: allowed_with_warnings
Compatible: True
Blockers: none
Warnings: 15 (missing contracts, event types, renderer hints)
```

### C — Future interactive stack (ICA 0.3.0 on Beta 0.2.0)
```
Decision: allowed_with_warnings
Compatible: True
Blockers: none
Warnings: 1 (optional web.crawl not available)
```

### D — Missing required web tool
```
Decision: denied
Compatible: False
Blockers: contract_version_mismatch, missing_tool, missing_capability
Missing req: web.fetch
Remediation: 4 items (install tool, adjust contract)
```

### E — Missing optional crawler
```
Decision: allowed
Compatible: True
Blockers: none
Warnings: none
```

### F — Unsupported interactive contract
```
Decision: denied
Compatible: False
Blockers: missing_contract (interactive_run_control)
Remediation: 2 items
```

### G — Beta renderer fallback
```
Decision: allowed_with_warnings
Compatible: True
Blockers: none
Warnings: 15 (contracts, events, renderer hints with fallback notes)
```

### H — Provider lacks structured output
```
Decision: denied
Compatible: False
Blockers: provider_lacks_capability (structured_output)
Warnings: 2 (context window, optional capability)
```

### I — Provider capability unknown (null flags)
```
Decision: indeterminate
Compatible: False
Blockers: contract_version_mismatch
Reasons: provider capability for structured output/tool calling is unknown
```

### J — Old Harness (no checkpoint, version 1.2.0)
```
Decision: denied
Compatible: False
Blockers: version_mismatch, harness_unsupported_by_beta, missing_tool, missing_capability
```

### K — v0.1 backward compatibility (pure v0.1 docs)
```
Decision: allowed
Compatible: True
Format: legacy nested matched (tools, capabilities, contracts)
Resolved versions: harness=1.3.2, beta=0.1.0, agent=0.1.0
```

## Security

### Secret rejection

All denylist patterns detected and rejected:

| Pattern | Detected | Nested detected |
|---------|----------|-----------------|
| `api_key` | ✓ | ✓ |
| `apikey` | ✓ | ✓ |
| `password` | ✓ | ✓ |
| `access_token` | ✓ | ✓ |
| `authorization` | ✓ | ✓ |
| `secret_key` | ✓ | ✓ |
| `bearer_token` | ✓ | ✓ |
| `credential` | ✓ | ✓ |

Allowlisted terms (`secret_policy`, `secret_ref_only`, `provider`, etc.) are not flagged.

### Malformed document handling

- `None` → error
- Non-dict → error
- Empty dict → error
- Missing required fields → error
- Additional properties (v0.2 schema) → error
- Duplicate conflicting capability declarations → handled (capabilities are sets, deduped)
- Duplicate component identities → duplicate_identity blocker (added in v0.2.1)
- Invalid version ranges → `match_range` returns `False`
- Invalid version strings → `parse_version` returns `()` → range fails

### Credential resolution

ARCP never reads or resolves actual credentials. The resolver is offline and deterministic — no network calls occur during resolution.

## Tests

| Metric | Value |
|--------|-------|
| Full suite | 175 passed |
| Failed | 0 |
| Skipped | 0 |
| Duration | 17.72s |
| Verification script | None (`scripts/verify.sh` does not exist) |
| Formatting/linting | Not configured in `pyproject.toml` |
| Type checking | Not configured in `pyproject.toml` |

### Real Harness v1.3.9 export validation (v0.2.1 update)

The real Harness v1.3.9 compatibility export (`harness compatibility export --format json`) produces a document in **transitional format** (v0.1 structure with `arcp_schema_version: "0.2"`). As of v0.2.1, ARCP auto-detects and normalizes these documents:
- `is_transitional_document()` detects the v0.1 structure + v0.2 label
- `normalize_transitional_document()` converts to native v0.2 format
- The normalized document passes validation and resolves correctly
- Updating the Harness export to produce native v0.2 is still recommended but no longer required

## Files changed

| File | Status |
|------|--------|
| `arcp/__init__.py` | Modified (v0.2 exports, version 0.2.0) |
| `arcp/models.py` | Modified (component types, contract families, capabilities) |
| `arcp/resolver.py` | Modified (v0.2 staged resolver + legacy compat) |
| `arcp/semver.py` | Modified (pre-release handling) |
| `arcp/validation.py` | Modified (v0.2 schema support, upgrade utility) |
| `arcp/cli.py` | Modified (environment resolution, exit codes) |
| `pyproject.toml` | Modified (version 0.2.0) |
| `schemas/compatibility_document_v0_2.schema.json` | New |
| `schemas/compatibility_resolution_v0_2.schema.json` | New |
| `README.md` | Updated |
| `spec/ARCP_0_2_SPEC.md` | New |
| `spec/ARCP_0_1_TO_0_2_MIGRATION.md` | New |
| `CHANGELOG.md` | New |
| `IMPLEMENTATION_REPORT.md` | New |
| `fixtures/*` | 10 fixtures + 5 environment files |
| `tests/test_v0_2.py` | New (86 tests) |

## Documentation

| Document | Location | Consistent |
|----------|----------|------------|
| Protocol specification | `spec/ARCP_0_2_SPEC.md` | ✓ |
| Migration guide | `spec/ARCP_0_1_TO_0_2_MIGRATION.md` | ✓ |
| Change log | `CHANGELOG.md` | ✓ |
| Implementation report | `IMPLEMENTATION_REPORT.md` | ✓ |
| README | `README.md` | ✓ |
| pyproject.toml | `pyproject.toml` | ✓ (v0.2.0; updated to 0.2.1 in hotfix) |

All documentation agrees on: protocol version 0.2, 6 component types, 4 decision names, canonical capability names, CLI syntax, v0.1 migration behavior, and out-of-scope declarations.

## Known limitations (v0.2.1)

1. **No `--version` CLI flag**: The CLI does not implement a `--version` flag; version is checked via `import arcp; arcp.__version__`.
2. **Deterministic only**: ARCP does not check live provider availability, network connectivity, or credential validity.
3. **Transitional Harness export now supported**: The Harness compatibility export transitional format is auto-detected and normalized. Updating the Harness export to produce native v0.2 is still recommended but no longer required.

## Recommended next step (v0.2.1)

Optionally update the Harness compatibility export (`build_harness_compatibility_document`) to produce native v0.2-format documents. The transitional format is supported but native v0.2 is cleaner.

## Tag recommendation

**v0.2.1** — hotfix release.

## Final acceptance (v0.2.1)

| Criterion | Status |
|-----------|--------|
| Transitional Harness v1.3.9 export validates and resolves | ✓ |
| Missing Beta contracts produce denial (not warnings) | ✓ |
| Missing optional capabilities produce `allowed_with_warnings` | ✓ |
| Duplicate component identities produce blocker | ✓ |
| All 175 tests pass | ✓ |
| All 30 scenario matrix checks pass | ✓ |
| v0.1 documents remain supported | ✓ |
| No merge or tag performed | ✓ |

**Overall status: READY**
