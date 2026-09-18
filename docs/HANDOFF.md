# QuotaPilot Development Handoff

> Shared current-state window for Claude Code and Codex. Read the technical
> design and decision log before continuing.

## Current state

- Date: 2026-09-18
- Last agent: Codex
- Current phase: **Phase 4 Budget Engine complete**
- Phase 2 provider boundary: **COMPLETE**
- Phase 3/3.1 persistence boundary: **COMPLETE**
- Phase 4 budget boundary: **COMPLETE**
- Phase 5 routing readiness: **READY**, but routing has not started
- Dependency direction remains:
  `CLI -> Services -> Budget -> Domain`, `Persistence -> Domain`,
  `Providers -> Domain`

The normative Phase 4 contract is
`docs/PHASE4_BUDGET_CONTRACT.md`.

## Phase 4 implementation

### Pure Budget Engine

- Added `src/quotapilot/budget/`:
  - `models.py`: `BudgetState`, `TimingSource`, `RemainingSource`,
    `WeekdayWeights`, `BudgetConfig`, `PoolBudgetAssessment`, `BudgetReport`.
  - `engine.py`: pure snapshot evaluation, expected pace, reserve, state,
    daily allocation, multi-window binding, stale warnings.
  - `errors.py`: exceptional caller-contract failures only.
- Inputs are only `UsageSnapshot`, `BudgetConfig`, and an aware evaluation
  time. The engine has no provider, RPC, SQLite, plan, or model-name imports.
- Same inputs produce equal reports. No internal clock calls exist.

### Timing and UNKNOWN semantics

- Valid start/reset computes clamped progress directly.
- Missing start plus reset and positive normalized `window_seconds` derives a
  start and records `timing_source=derived_window_seconds`.
- Reset-only pools do not fabricate a start and remain UNKNOWN for pace, but
  can report remaining quota, reset time, and daily allocation.
- Start-only/no-timing/zero-length timing remains UNKNOWN with explicit
  warnings.
- Unknown `kind`/`scope` alone does not discard otherwise safe calculations.

### Policy and allocation

- Reserve defaults to 10%, constrained to `[0, 1)`.
- Configurable state thresholds implement VERY_UNDER/UNDER/ON_TRACK/OVER/
  CRITICAL; UNKNOWN has no pressure.
- Pressure defaults are `0.00/0.15/0.35/0.70/1.00` and configurable.
- Daily allocation uses explicit IANA timezone (default UTC), configurable
  weekday weights, inclusive current/reset dates, and deterministic midnight
  reset handling. No hourly optimizer exists.
- Multi-window pressure is the maximum known pressure. Tie-break is pressure
  descending, remaining ascending, pool ID ascending. UNKNOWN pools remain
  visible and do not become the maximum automatically.

### Staleness, service, and CLI

- Default stale threshold is 900 seconds. Stale and future-captured snapshots
  return reports with prominent warnings; the engine never refreshes data.
- Added `BudgetService`: latest repository snapshot -> pure evaluation.
- Added `quotapilot budget` and `quotapilot budget --json`.
- Human output renders unknown calculations as `unavailable`/`UNKNOWN`.
- JSON is the Pydantic `BudgetReport`; it excludes account ID, plan name, raw
  observation metadata, credentials, and routing advice.

## Test coverage and verification

Commands run from the repository root:

```bash
uv run pytest
uv run ruff check .
uv run pyright
uv run quotapilot --help
uv run quotapilot budget --help
QUOTAPILOT_INTEGRATION=1 uv run pytest tests/integration/
```

Results:

- Offline/default pytest: **238 passed, 5 skipped**. The five skips are the
  explicitly gated authenticated integration suite.
- Ruff: **All checks passed**.
- Pyright: **0 errors, 0 warnings, 0 informations**.
- Root and budget CLI help: **PASS**.
- Live integration: **5 passed**. Existing live capture -> temporary SQLite
  -> privacy-safe reload now also evaluates a BudgetReport and verifies report
  bounds. Unknown timing remains acceptable; no semantic fallback was added to
  improve live appearance.

New deterministic coverage includes:

- beginning/midpoint/near-reset/before-start/after-reset/zero-length windows,
- reset-only/start-only/no-timing and derived starts,
- reserve and exact state-threshold boundaries,
- equal/unequal weekday weights, final/partial/midnight reset days,
- both directions of short-window/weekly binding, UNKNOWN+known pools, ties,
- fresh/stale/future snapshots and repeated-input determinism,
- save -> reload -> evaluate equivalence,
- human/JSON CLI, no-data behavior, and JSON privacy.

Normal CI remains offline and credential-free.

## Privacy/security state

- Phase 3.1 account pseudonymization remains unchanged.
- Budget code cannot access provider auth/transport or raw metadata.
- `BudgetReport` has no account or plan field; CLI tests assert private
  account/plan values are absent from JSON.
- No live provider values, credentials, cookies, or auth files were written or
  printed by Phase 4 tests.

## Remaining risks / deferred decisions

- `window_seconds` correctness is owned by provider normalization. The engine
  consumes a positive normalized duration but never infers one from names or
  past observations.
- Default calendar timezone is UTC. Loading user YAML/config precedence is a
  separate configuration-layer task; CLI flags already expose timezone,
  reserve, and staleness policy.
- Phase 4 evaluates the latest point-in-time snapshot. Historical trend-based
  forecasting remains future work.
- A reset-only pool can receive a daily allocation but intentionally cannot
  receive known pace pressure.
- Long-lived versus ephemeral Codex app-server lifecycle remains deferred.

## Next task

Phase 5 may implement provider-independent routing using
`BudgetReport.effective_pressure` and normalized capabilities. It must not
import provider RPC or SQLite internals and must keep UNKNOWN pressure explicit.
No model recommendation, effort selection, scoring, or escalation exists yet.
