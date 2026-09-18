# QuotaPilot Development Handoff

> Shared current-state window for Claude Code and Codex. Read the technical
> design and decision log before continuing.

## Current state

- Date: 2026-09-18
- Last agent: Codex
- Current phase: **Phase 4.1 Budget Engine stabilization complete**
- Phase 2 provider boundary: **COMPLETE**
- Phase 3/3.1 persistence boundary: **COMPLETE**
- Phase 4/4.1 budget boundary: **COMPLETE**
- Phase 5 routing readiness: **READY**, but routing has not started
- Dependency direction remains:
  `CLI -> Services -> Budget -> Domain`, `Persistence -> Domain`,
  `Providers -> Domain`

The normative budget contract is `docs/PHASE4_BUDGET_CONTRACT.md`.

## Phase 4.1 stabilization

### UTC instant arithmetic

- All duration and ordering operations normalize operands to UTC first:
  window progress/duration, time until reset, snapshot age, future/before/
  after checks, and derived starts.
- Configured local timezone is used only for calendar-day bucket semantics.
- `resets_at - window_seconds` now subtracts from `reset_utc`, so 86400 means
  exactly 86400 elapsed seconds across 23/25-hour DST days.
- Regression coverage includes the 2026 America/New_York spring gap, both
  fall folds, time-to-reset, snapshot age/future detection, and derived
  windows. The review example evaluates to `11/23` progress,
  `pace_delta ~= 0.0717391304`, and `OVER`.

### Exact state thresholds

- Removed tolerance/`math.isclose` logic from state classification.
- Direct comparisons now exactly implement the documented inclusive/exclusive
  boundaries at `-0.20`, `-0.07`, `0.07`, and `0.20`.
- `math.nextafter()` tests exercise the immediate representable float on both
  sides of every threshold.

### Strict policy configuration

- `BudgetConfig` and `WeekdayWeights` now use strict Pydantic validation with
  `extra="forbid"` while remaining frozen.
- Numeric strings, booleans/floats supplied as integers, unknown keys, typo
  keys, invalid timezone/order/weights, NaN, and infinity are rejected.
- Intentional YAML/environment conversion remains the responsibility of a
  future config-loader boundary.

### O(1) calendar allocation

- Daily allocation no longer constructs one `date` per remaining day.
- Total weight is complete weeks times the seven-day sum plus at most six
  remainder weekdays; runtime is independent of reset distance.
- Existing current-day, reset-day, midnight, timezone, and weight semantics
  are unchanged. Tests cover 7/30-day intervals, a brute-force reference,
  multi-year resets, `datetime.max`, and multiple pools.

## Verification

Commands run from the repository root:

```bash
uv run pytest
uv run ruff check .
uv run pyright
uv run quotapilot budget --help
QUOTAPILOT_INTEGRATION=1 uv run pytest tests/integration/
```

Results:

- Offline/default pytest: **256 passed, 5 skipped**. The skips are the
  explicitly gated authenticated integration suite.
- Focused Budget Engine tests: **63 passed**.
- Ruff: **All checks passed**.
- Pyright: **0 errors, 0 warnings, 0 informations**.
- Budget CLI help: **PASS**.
- Live integration: **5 passed**. Live capture -> temporary SQLite -> reload
  -> BudgetReport remains successful; no provider semantics were changed to
  make live results appear richer.

Normal CI remains offline and credential-free.

## Privacy/security state

- Phase 3.1 account pseudonymization and provider redaction are unchanged.
- Budget code still imports no provider, RPC, auth, or SQLite implementation.
- No account identifiers, live telemetry, credentials, cookies, or auth files
  were added or printed by Phase 4.1.
- No model/effort recommendation, scoring, escalation, or automatic routing
  code exists.

## Remaining risks / deferred decisions

- `window_seconds` correctness remains owned by provider normalization; the
  engine treats a positive normalized duration as elapsed seconds.
- Calendar timezone defaults to UTC. YAML/environment config loading and
  precedence remain future configuration-layer work.
- Historical trend forecasting remains future work; Phase 4 evaluates the
  latest coherent point-in-time snapshot.
- Reset-only pools intentionally have no pace pressure even though they may
  receive a calendar-day allocation.
- Long-lived versus ephemeral Codex app-server lifecycle remains deferred.

## Next task

Phase 5 may implement provider-independent routing using
`BudgetReport.effective_pressure` and normalized capabilities. It must keep
UNKNOWN pressure explicit and must not import provider RPC or SQLite internals.
