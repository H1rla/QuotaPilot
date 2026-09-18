# QuotaPilot Development Handoff

> Shared current-state window for Claude Code and Codex. Read the technical
> design, phase contracts, and decision log before continuing.

## Current state

- Date: 2026-09-18
- Last agent: Codex
- Current phase: **Phase 8 desktop GUI complete; release-candidate verification next**
- Phase 2 provider boundary: **COMPLETE**
- Phase 3/3.1 persistence boundary: **COMPLETE**
- Phase 4/4.1 budget boundary: **COMPLETE**
- Phase 5 routing boundary: **COMPLETE**
- Phase 5.5 enrichment/calibration boundary: **COMPLETE**
- Phase 6 controlled execution boundary: **COMPLETE**
- Phase 7 productization/release-readiness boundary: **COMPLETE**
- Phase 8 PySide6/QML GUI boundary: **COMPLETE**
- Release readiness: **GUI gate passed; final user-approved RC/release gate pending**
- Publishing/tag/GitHub release: **NOT PERFORMED**

The implemented Phase 7 contract is
`docs/PHASE7_PRODUCTIZATION_CONTRACT.md`. The reusable pre-publication gate is
`docs/RELEASE_CHECKLIST.md`.

The implemented Phase 8 contract is `docs/PHASE8_GUI_CONTRACT.md`; its visual
authority is `docs/UI_DESIGN.md` plus the local `quotapilot-ui` Skill.

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

## Phase 8 implementation

### Desktop architecture and async boundary

- `src/quotapilot/gui/` is a PySide6/Qt Quick presentation layer over the
  existing services. `dependencies.py` is the composition root; QML never
  reads SQLite, calls provider RPC, performs budget/routing math, or invokes
  `quotapilot` as a subprocess.
- Provider refresh, SQLite history, routing, execution planning, and controlled
  execution run through `AsyncRunner` workers on `QThreadPool`, each with its
  own asyncio loop. Qt's main thread only maps and renders returned state.
- `quotapilot gui` is registered through a lazy CLI import. Existing non-GUI
  commands do not import PySide6.

### Screens and interaction

- Seven QML screens are present: Overview, Usage, Models, Route, Execute,
  History, and Settings. Shared components and all color/spacing/radius/type/
  motion values live under `gui/qml/components/` and `gui/qml/Tokens.js`.
- Overview uses one technical workspace rather than KPI cards. UNKNOWN and
  STALE remain explicit; green is limited to interaction/selection/actual
  usage while warning/error states keep semantic colors and text.
- Usage/History use only persisted snapshots and do not interpolate missing
  points. Models exposes exact IDs, routability, profile freshness,
  provenance, confidence, evidence, and supported effort order.
- Route analysis never executes. Execute separately builds and displays the
  complete Phase 6 plan, directory-modification warning, dry-run action, and
  explicit approval action. A changed escalation is never implicitly approved.
- `Ctrl+P`, `Ctrl+R`, `Ctrl+D`, `Ctrl+,`, `Esc`, Enter, and palette arrow
  navigation are wired. The palette contains navigation and safe actions only.
- Settings searches all required categories and saves common strict policy
  values atomically through `save_user_config`; changes apply on next launch.
  No provider credential or arbitrary environment value is written.

### Packaging and tests

- PySide6 is a runtime dependency. QML/JS assets are normal package data and
  were verified inside the built wheel. An isolated wheel installation passed
  `quotapilot --version`, `quotapilot gui --smoke-test`, and resource lookup.
- `tests/unit/test_gui_phase8.py` covers mappings, UNKNOWN, STALE, provider
  unavailable, no snapshot/no route, routing, dry-run, approval-required plans,
  invalid settings, command actions, privacy, and offscreen QML loading.
- Full-engine smoke exposed a QML `state` role collision with QQuickItem; roles
  are now named `statusValue`/`statusText`, recorded in `lessons.md`.

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
uv run quotapilot gui --smoke-test
QUOTAPILOT_INTEGRATION=1 uv run pytest tests/integration/
```

Results:

- Offline/default pytest: **431 passed, 5 skipped**. The skips are the five
  explicitly gated authenticated tests.
- Normal authenticated integration: **5 passed**. It captured quota/models and
  exercised persistence/budget/enrichment/routing only; no model execution.
- Ruff: **All checks passed**.
- Pyright: **0 errors, 0 warnings, 0 informations**.
- Build: **wheel and sdist succeeded**.
- Clean-wheel and isolated `uv tool` smoke: **PASS**.
- QML offscreen smoke, installed-wheel GUI smoke, and real Wayland launch:
  **PASS**. Overview was visually checked at **1100x720** and **900x600**.
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
- GUI settings changes are persisted atomically but intentionally take effect
  on the next launch; an active service graph is not partially reconfigured.

## Next task

Perform final release-candidate verification, including user interaction review
on the target desktop and observation/calibration of recommendations, without
widening the Phase 6 authorization boundary. A release tag, GitHub release, or
package publication requires separate explicit user authorization.
