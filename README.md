# ARCP — Agent Runtime Compatibility Protocol

**Version 0.1**

ARCP is a small open-source protocol and library that defines how agent runtimes
(Harness, Workbench Beta, and agents) declare compatibility requirements, and how
a deterministic resolver decides whether a specific combination is compatible.

## Why deterministic compatibility?

- **No LLM in the loop** — compatibility is decided by a static resolver, not an
  AI judge. This makes ARCP suitable for pre-flight checks, CI/CD gates, and
  audit trails.
- **Structured blockers** — when a combination is incompatible, ARCP produces a
  list of typed, machine-readable blockers with suggested actions, not a vague
  text explanation.
- **JSON in, JSON out** — every document and resolution is a plain JSON file.
  No database, no server, no network calls.

## Install / dev setup

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/).

```bash
# Clone the repo
cd arcp

# Install dependencies (jsonschema)
uv sync

# Run the tests
uv run pytest -v
```

## CLI usage

### Validate a compatibility document

```bash
uv run arcp validate --input examples/harness_1_3_2.compat.json
```

### Resolve compatibility

```bash
uv run arcp resolve \
  --harness examples/harness_1_3_2.compat.json \
  --beta examples/workbench_beta_0_1.compat.json \
  --agent examples/live_llm_reference_agent_0_1.compat.json \
  --format json
```

### Explain a resolution

```bash
uv run arcp explain --resolution examples/compatible_resolution.json
```

## Document kinds

| Kind      | Description                                      |
|-----------|--------------------------------------------------|
| `harness` | What the agent runtime provides (tools, caps)    |
| `beta`    | What the workbench supports / renders            |
| `agent`   | What the agent requires to run                   |

## Resolver decision model

The resolver checks:

1. **Version ranges** — agent requires harness X, beta supports harness Y
2. **Tools** — every tool the agent requires is provided by harness and beta
3. **Capabilities** — every capability the agent requires is present in both
4. **Contracts** — every contract the agent needs is provided by harness and
   supported by beta
5. **Event types** — required event types are emitted by harness

If any check fails, the resolution is `blocked` with a structured list of
`blockers`. Non-fatal mismatches produce `warnings`. The output is always
deterministic, JSON-serialisable, and consumable by tooling.

## Example commands

```bash
# Validate all example documents
uv run arcp validate --input examples/harness_1_3_2.compat.json
uv run arcp validate --input examples/workbench_beta_0_1.compat.json
uv run arcp validate --input examples/live_llm_reference_agent_0_1.compat.json

# Resolve compatibility for the reference agent
uv run arcp resolve \
  --harness examples/harness_1_3_2.compat.json \
  --beta examples/workbench_beta_0_1.compat.json \
  --agent examples/live_llm_reference_agent_0_1.compat.json \
  --format json
```

## Non-goals

- ARCP server
- Docker service
- Harness integration
- Workbench Beta UI
- Agent runtime
- LLM compatibility judge
- Marketplace / billing / entitlements
- Remote code execution
- Network calls

## License

Apache 2.0
