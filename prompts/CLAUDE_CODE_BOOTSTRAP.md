# Claude Code Bootstrap Prompt — QuotaPilot

You are the first implementation agent for the QuotaPilot repository.

Repository:

```text
/home/hira/main/projects/tools/QuotaPilot
```

The repository is currently expected to be empty except for the design/handoff files supplied by the user.

## Read first

Before changing anything, read these files completely:

1. `docs/TECHNICAL_DESIGN.md`
2. `docs/DECISIONS.md`
3. `docs/HANDOFF.md`
4. `CLAUDE.md`
5. `docs/IMPLEMENTATION_PLAN.md`

Treat `docs/TECHNICAL_DESIGN.md` as the canonical design.

## Goal for this session

Implement:

- Phase 0 — repository bootstrap
- Phase 1 — domain layer

After both phases pass their exit criteria, you may begin **Phase 2A only** if there is still sufficient context and the repository is healthy.

Do **not** implement the budget engine, routing engine, Waybar integration, or automatic model selection in this session.

## Phase 0 requirements

Create a clean Python 3.12+ project using a `src/` layout.

Use:

- `pyproject.toml`
- `uv`-friendly packaging
- pytest
- ruff
- pyright or mypy
- Typer for the future CLI
- GitHub Actions for offline lint/type/test checks

Create a minimal `quotapilot` CLI entry point such that:

```bash
quotapilot --help
```

works after installation.

Do not add dependencies that are not currently needed.

Do not create placeholder implementation files for every future component just to mirror the final tree.

## Phase 1 requirements

Implement provider-independent domain models described in the design:

- AccountInfo
- AIModel
- CapabilitySet
- QuotaPool
- QuotaBinding
- UsageSnapshot

Also define the minimal provider protocol/base types needed by the architecture.

Use Pydantic v2.

Requirements:

- strict enough validation to catch invalid fractions/ranges,
- timezone-aware datetimes where applicable,
- unknown provider metadata can be preserved,
- domain package must not import OpenAI/Codex-specific modules,
- no plan-specific branching in the domain layer.

Add focused unit tests.

## Phase 2A, only if appropriate

If Phase 0 and Phase 1 are fully green, you may create the OpenAI Codex provider package and implement only the process/RPC transport foundation needed to communicate with the installed `codex app-server`.

Before assuming any RPC method name or schema:

- inspect the installed Codex CLI behavior/help where practical,
- distinguish verified behavior from assumptions,
- do not persist authentication material,
- do not scrape browser sessions.

Do not yet implement budget/routing logic.

## Engineering rules

Keep the implementation minimal.

Do not over-engineer.

Do not refactor unrelated files.

Prefer pure, typed, testable code.

Preserve this dependency direction:

```text
CLI -> Services -> Budget / Routing -> Domain
Providers -> Domain
Persistence -> Domain
```

Never create:

```text
Domain -> OpenAI
Budget -> Codex RPC
Routing -> SQLite
Provider -> CLI
```

## Verification before finishing

Run the relevant commands for:

- tests,
- lint,
- type checking,
- CLI help/import smoke test.

Fix failures that are caused by your work.

Do not weaken tests merely to make the suite green.

## Mandatory handoff

Before ending the session, update:

```text
docs/HANDOFF.md
```

with:

- phases completed,
- exact files changed,
- exact verification commands and results,
- any live Codex behavior learned,
- blockers/open questions,
- the next concrete task.

If you make an architectural decision not already covered by the design, append it to:

```text
docs/DECISIONS.md
```

Do not rewrite prior decisions silently.

At the end, give the user a concise summary of:

1. what was implemented,
2. test/lint/type-check status,
3. whether Phase 2A was started,
4. what the next agent should do.
