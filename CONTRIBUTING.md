# Contributing to QuotaPilot

## Development setup

QuotaPilot requires Python 3.12 or newer and uses `uv` in development.

```bash
git clone git@github.com:H1rla/QuotaPilot.git
cd QuotaPilot
uv sync --dev
uv run pytest
uv run ruff check .
uv run pyright
uv build
```

## Architecture boundaries

Preserve these dependency directions:

```text
CLI -> Services -> Budget / Routing -> Domain
Providers -> Domain
Persistence -> Domain
Execution adapters -> external tools
```

Do not introduce provider RPC into budget/routing, SQLite into routing, model
name policy into the routing engine, or subprocess behavior into generic
execution policy/planning.

## Contracts and decisions

Read `AGENTS.md`, `docs/TECHNICAL_DESIGN.md`, the current phase contract, and
`docs/DECISIONS.md` before implementation. Contract changes must be explicit.
Append durable decisions instead of rewriting history. Update
`docs/HANDOFF.md` after meaningful work.

## Tests

Normal `pytest` and CI must be offline and credential-free. Use fake adapters
for execution tests. `QUOTAPILOT_INTEGRATION=1` gates authenticated provider
tests and must never perform real coding-agent execution.
`QUOTAPILOT_EXECUTION_INTEGRATION=1` is a separate explicit gate for any
future narrowly scoped real-execution test.

## Privacy and fixtures

Never commit credentials, browser cookies, raw account IDs, private tasks,
full transcripts, real private usage telemetry, local databases, or user
configuration. Provider fixtures must be synthetic or sanitized, structurally
faithful, and documented in their `PROVENANCE.md`. Run fixture/privacy tests
before proposing changes.

## Model profiles

Model-specific routing metadata belongs under `policies/model_profiles/`, not
in the routing engine. Match exact model IDs, preserve provider truth, attach
human-readable provenance/confidence, use an expiry boundary, and leave fields
unknown when evidence is weak. Run deterministic calibration after changes.

## Pull-request checklist

- Keep the diff scoped and add regression coverage.
- Run pytest, Ruff, Pyright, and `uv build`.
- Confirm normal tests do not invoke Codex or access user config/data.
- Review machine JSON and diagnostics for private data.
- Update relevant contracts, decisions, handoff, and user docs.
