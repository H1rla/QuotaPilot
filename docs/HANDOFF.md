# QuotaPilot Development Handoff

> Shared current-state window for Claude Code and Codex. Read the technical
> design, phase contracts, and decision log before continuing.

## Current state

- Date: 2026-09-18
- Last agent: Codex
- Current phase: **Phase 7 productization complete**
- Phase 2 provider boundary: **COMPLETE**
- Phase 3/3.1 persistence boundary: **COMPLETE**
- Phase 4/4.1 budget boundary: **COMPLETE**
- Phase 5 routing boundary: **COMPLETE**
- Phase 5.5 enrichment/calibration boundary: **COMPLETE**
- Phase 6 controlled execution boundary: **COMPLETE**
- Phase 7 productization/release-readiness boundary: **COMPLETE**
- Release readiness: **READY**
- Publishing/tag/GitHub release: **NOT PERFORMED**

The implemented Phase 7 contract is
`docs/PHASE7_PRODUCTIZATION_CONTRACT.md`. The reusable pre-publication gate is
`docs/RELEASE_CHECKLIST.md`.

## Phase 7 implementation

### Strict central configuration

- `src/quotapilot/config/` loads optional safe YAML from the platformdirs user
  config path and validates one strict `AppConfig` (`extra="forbid"`).
- Existing `BudgetConfig`, `RoutingPolicy`, and `ExecutionPolicy` are embedded;
  no duplicate policy schema was introduced.
- Precedence is CLI > selected `QUOTAPILOT_*` environment variables > user
  config > policy defaults > built-ins. String/enum conversion happens
  explicitly at the loader boundary before strict validation.
- `quotapilot config show [--json]` reports effective field sources;
  `config validate [--json]` performs no provider or execution access.
- Budget, route, models, snapshot, and execute commands now consume central
  database/provider/profile/policy settings while preserving their CLI
  overrides.

### Status and Waybar

- `StatusService` composes repository snapshots, the existing Budget Engine,
  and capability enrichment into strict privacy-safe status models. It does
  not expose account IDs, plan labels, raw observations, or raw capability
  metadata.
- `quotapilot status [--json]` defaults to persisted state. `--refresh`
  performs one explicit coherent Codex capture/store; on failure it retains and
  labels a `persisted_fallback` rather than presenting cached data as live.
- `quotapilot waybar` is persisted-only and produced in about 0.30 seconds in
  a clean no-snapshot smoke. Stable classes are `very-under`, `under`,
  `on-track`, `over`, `critical`, `unknown`, `stale`, and `error`.
- Waybar never contacts the provider or execution adapter, and every failure
  path returns one generic valid JSON object with exit code 0.

### Doctor and output UX

- `quotapilot doctor [--json]` returns PASS/WARN/FAIL/SKIP checks for runtime,
  strict config, database/schema, Codex executable/version/auth/app-server,
  model profiles/freshness, routable models, provider capture, Waybar, and the
  execution adapter.
- Default doctor does not capture provider data; `--live` is explicit.
  Authentication command output is discarded, and raw exceptions/environment
  values are never reflected in diagnostics.
- Root `--version` reads installed package metadata (`0.1.0`), while the
  existing `version` command remains compatible. `--debug` enables standard
  stderr logging; application JSON remains plain JSON without ANSI markup.
- No execution-history command was added because Phase 6 persists no audit.

### Packaging and repository readiness

- `uv build` creates a wheel and sdist. The wheel contains the bundled exact-ID
  model profiles, calibration scenarios, package metadata, and MIT license; it
  contains no fixtures, DB, config, caches, venv, or Git data.
- A clean temporary venv installed the wheel and passed `--version`, `--help`,
  config validation, bundled profile loading, and calibration replay.
- An isolated `uv tool install` of the wheel also passed `quotapilot --version`.
- CI now runs pytest, Ruff, Pyright, CLI/calibration smoke, build, isolated
  wheel installation, and installed-resource smoke. It sets neither live
  integration gate nor execution integration gate.
- README is user-facing and documents verified wheel installation, quick
  start, strict config/environment overrides, data locations, Waybar, safety,
  privacy, compatibility, and architecture.
- `CHANGELOG.md`, `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, and the release
  checklist are present. No third-party copied/adapted source requiring a
  NOTICE was found; dependencies are not vendored.

## Verification

Commands run from the repository root:

```bash
uv run pytest
uv run ruff check .
uv run pyright
uv build
uv run quotapilot --version
uv run quotapilot --help
uv run quotapilot status --help
uv run quotapilot doctor --help
uv run quotapilot waybar --help
uv run quotapilot config --help
uv run quotapilot models --help
uv run quotapilot execute --help
QUOTAPILOT_INTEGRATION=1 uv run pytest tests/integration/
```

Results:

- Offline/default pytest: **423 passed, 5 skipped**. The skips are the five
  explicitly gated authenticated tests.
- Normal authenticated integration: **5 passed**. It captured quota/models and
  exercised persistence/budget/enrichment/routing only; no model execution.
- Ruff: **All checks passed**.
- Pyright: **0 errors, 0 warnings, 0 informations**.
- Build: **wheel and sdist succeeded**.
- Clean-wheel and isolated `uv tool` smoke: **PASS**.
- Calibration: **10/10 acceptable hits**, zero recorded violations.
- Real execution integration: **NOT RUN** and not required for Phase 7.

## Security/privacy review

- Safe YAML loaders remain in use; strict config rejects unknown keys and
  coercible policy values. No arbitrary environment-to-command setting exists.
- Provider/execution subprocesses use argument vectors, never shell task
  interpolation. Phase 7 added no execution subprocess path.
- Fake token/API-key/authorization/account values do not appear in doctor
  output. Status and Waybar regression tests exclude account identity, plan,
  and raw observations while preserving `null`, zero, UNKNOWN, and stale.
- Repository/distribution scans found no credential, real account identity,
  private usage telemetry, raw task, local DB, cache, or virtualenv artifact.
- Normal CI and default pytest cannot execute a paid/real model.

## Remaining limitations

- Linux/Python 3.12 is the verified platform; macOS/Windows are not claimed.
- OpenAI Codex is the only live provider and execution adapter.
- Capability scores remain provisional policy, not empirical guarantees.
- Waybar intentionally reflects the latest persisted snapshot; users must run
  capture/status refresh separately to update it.
- Doctor's non-live auth check depends on the installed Codex CLI's stable
  `login status` behavior; it discards all command output.
- Execution audit persistence, background refresh/daemon, TUI, notifications,
  migration version 2, and publishing remain unimplemented by design.

## Next task

Use an observation/calibration period to compare advisory recommendations with
real outcomes without widening the Phase 6 authorization boundary. A release
tag, GitHub release, or package publication requires separate explicit user
authorization.
