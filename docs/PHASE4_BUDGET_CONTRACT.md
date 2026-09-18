# QuotaPilot Phase 4 Budget Contract

## 1. Purpose and boundary

Phase 4 answers, from one normalized `UsageSnapshot`:

* how much quota is consumed,
* how much usable quota should ideally have been consumed by now,
* whether consumption is ahead of or behind policy pace,
* how much reserve-aware quota may be used today,
* which evaluable quota pool is the current binding constraint.

The core API is pure:

```text
UsageSnapshot + BudgetConfig + aware evaluation time
    -> BudgetEngine.evaluate()
    -> BudgetReport
```

The Budget Engine imports domain objects only. It does not call providers,
read RPC responses, query SQLite, inspect plan names, or fetch fresh data.
A service may load the latest snapshot from `SnapshotRepository` and then call
the engine.

## 2. Explicit non-goals

Phase 4 does not implement:

* model or reasoning-effort recommendations,
* model scoring or utility,
* task classification,
* escalation,
* automatic model execution or delegation,
* provider refresh inside the mathematical engine,
* hourly optimization,
* inference from Go/Plus/Pro or any model name.

These are Phase 5 or later concerns.

## 3. Inputs and deterministic evaluation

`BudgetEngine.evaluate(snapshot, now)` requires an aware `now`. The engine
never calls `datetime.now()` internally. Equal snapshot, config, and `now`
must produce equal reports.

`UsageSnapshot.captured_at` is already aware by domain validation. Duplicate
pool IDs are rejected as an inconsistent input because deterministic binding
selection would otherwise be ambiguous.

All elapsed-time arithmetic and ordering use UTC-normalized instants. This
includes window duration/progress, time until reset, snapshot age,
before/after comparisons, and derived starts. The configured local timezone
is used only for calendar semantics: weekday selection, local reset date, and
daily allocation buckets. Aware datetimes must never be subtracted in local
wall-clock form across a daylight-saving transition.

## 4. Budget state

```text
VERY_UNDER
UNDER
ON_TRACK
OVER
CRITICAL
UNKNOWN
```

`UNKNOWN` is a valid result, not an error. Missing usage, insufficient timing,
and invalid/unknown period semantics must not be forced into a known state.

## 5. Actual usage and remaining quota

For a pool with normalized `used_fraction`:

```text
actual_usage = used_fraction
```

The domain guarantees `0 <= used_fraction <= 1`. The Budget Engine never
clamps malformed provider usage.

Remaining quota uses this order:

1. `QuotaPool.remaining_fraction`, with source `reported`;
2. if absent and `used_fraction` exists, `1 - used_fraction`, with source
   `derived_used_fraction`;
3. otherwise unavailable.

If reported used and remaining values are not complementary, both are
preserved and a warning is emitted. The engine does not silently repair
provider data.

## 6. Reserve policy

`reserve_fraction` is user policy, not provider truth. Default:

```text
reserve_fraction = 0.10
usable_quota = 1 - reserve_fraction
```

Constraint:

```text
0 <= reserve_fraction < 1
```

Reserve-aware currently available quota is measured on the total quota scale:

```text
available_fraction = max(0, remaining_fraction - reserve_fraction)
```

If remaining quota is unavailable, available quota is unavailable.

## 7. Supported timing semantics

Timing is evaluated independently of `QuotaPool.kind` and `scope`. Unknown
kind/scope does not exclude a pool when the numeric and temporal fields needed
for a calculation are present.

### 7.1 Start and reset present

When `starts_at` and `resets_at` are present and `resets_at > starts_at`:

```text
start = starts_at
reset = resets_at
timing_source = start_reset
```

The comparison and all subsequent duration arithmetic operate on the UTC
instants represented by these timestamps, not their local wall-clock values.

`start_reset` describes which normalized domain fields the budget calculation
used; it does not claim the provider directly reported the start. Provider
adapters retain their own fact/inference provenance in pool metadata.

### 7.2 Reset and positive window duration present

When start is absent, but reset and a strictly positive normalized
`window_seconds` are present:

```text
start = resets_at - window_seconds
reset = resets_at
timing_source = derived_window_seconds
```

The reset is first normalized to UTC, then `window_seconds` is subtracted as
elapsed seconds. Thus a duration of 86400 is exactly 24 elapsed hours even
when the corresponding local wall-clock interval crosses a 23- or 25-hour
day. The source is explicitly derived. A provider adapter must leave
`window_seconds=None` when it cannot establish a duration; the Budget Engine
does not infer duration from names, kinds, scopes, or prior snapshots.

### 7.3 Reset only

With only `resets_at`, the engine reports remaining/available quota and time
until reset. It may allocate the available quota across remaining calendar
days because that operation needs a reset boundary but not an elapsed-period
origin. It does not calculate window progress, expected usage, pace delta, or
a known state.

### 7.4 Start only or no timing

Expected usage, pace, time until reset, and daily budget are unavailable.

### 7.5 Invalid or zero-length timing

`resets_at <= starts_at`, or `window_seconds <= 0` when it is the only way to
derive a start, makes pace timing unavailable and emits a warning. Ordinary
unknown timing is represented in the report rather than raised as an
exception.

## 8. Window progress and expected usage

For valid start/reset timing:

```text
window_progress = (now - start) / (reset - start)
window_progress = clamp(window_progress, 0, 1)
expected_usage = window_progress * (1 - reserve_fraction)
```

`now`, `start`, and `reset` are UTC-normalized instants for this arithmetic.

Before start, progress is `0`; after reset, progress is `1`. Both conditions
emit warnings. A past reset has no daily budget remaining, but the historical
pace calculation remains deterministic.

Expected usage may be present when actual usage is absent. Pace delta and a
known state require both.

## 9. Pace delta and state thresholds

```text
pace_delta = actual_usage - expected_usage
```

Default configurable thresholds:

```text
VERY_UNDER  delta < -0.20
UNDER      -0.20 <= delta < -0.07
ON_TRACK   -0.07 <= delta <= 0.07
OVER        0.07 < delta <= 0.20
CRITICAL    0.20 < delta
```

Classification uses these direct comparisons exactly. There is no tolerance,
`isclose` band, rounding, or implicit quantization around a threshold.

Threshold ordering must be strict:

```text
very_under_threshold
    < under_threshold
    < over_threshold
    < critical_threshold
```

Underuse is a valid low-pressure state, not an error.

## 10. Pressure policy

Known states map to configurable policy pressure:

```text
VERY_UNDER -> 0.00
UNDER      -> 0.15
ON_TRACK   -> 0.35
OVER       -> 0.70
CRITICAL   -> 1.00
UNKNOWN    -> None
```

Known pressure values are constrained to `[0, 1]` and must be non-decreasing
in the order above.

## 11. Daily budget

Daily allocation requires available quota and a future reset. It does not
require a known start. It uses an explicit IANA timezone from `BudgetConfig`;
the default is `UTC`, avoiding process-local hidden state.

Default weekday weights are all `1.0`. Weights are finite, non-negative, and
at least one configured weekday weight must be positive.

Remaining allocation dates are determined as follows:

1. The current local calendar day counts as one full weighted day; elapsed
   hours are deliberately ignored in v0.1.
2. Dates through the local reset date are included.
3. If reset occurs exactly at local `00:00:00`, the reset date is excluded;
   otherwise the reset date counts as one full weighted day.
4. If reset is at or before `now`, today's budget is `0`.
5. If a known/derived start is in the future, today's budget is unavailable
   because the quota period is not active.

For included dates:

```text
today_budget_fraction =
    available_fraction
    * today_weight
    / sum(remaining_day_weights)
```

The denominator is computed in constant time with respect to interval length:
complete seven-day weeks contribute `week_count * sum(weekday_weights)`, and
only the at-most-six remaining weekdays are inspected. The implementation
must not materialize one object per remaining calendar date.

If all remaining dates have zero weight, today's budget is unavailable and a
warning is emitted. Therefore:

```text
0 <= today_budget_fraction <= available_fraction
```

## 12. Pool eligibility and UNKNOWN behavior

Every input pool produces a `PoolBudgetAssessment`; no unknown pool is
silently dropped.

Calculations are independently eligible:

* actual usage: `used_fraction` exists;
* remaining/available: reported remaining exists, or used exists;
* expected pace/state/pressure: valid period timing exists and actual usage
  exists;
* daily budget: available quota and a future reset exist, and the period is
  not known to start in the future.

Unknown kind/scope alone never excludes otherwise usable numeric data. No
scope-based applicability or model semantics are inferred in Phase 4.

## 13. Multi-window pressure and binding pool

Each pool is assessed independently. Effective pressure is the maximum known
pool pressure; pressures are never averaged.

`UNKNOWN` pools have `pressure=None`, remain visible, and do not automatically
become the maximum. If no pool has known pressure:

```text
effective_pressure = None
binding_pool_id = None
```

Binding selection is deterministic:

```text
pressure DESC
remaining_fraction ASC  (None sorts after known values)
pool_id ASC
```

The binding pool is a quota constraint only. It is not a model recommendation.

## 14. Snapshot age and no-data behavior

Default:

```text
stale_after_seconds = 900
```

Snapshot age is `now_utc - captured_at_utc`, using elapsed instants rather
than local wall-clock subtraction.

* Age greater than the configured threshold returns a normal report with
  `is_stale=True` and `snapshot_stale` warning.
* A future `captured_at` returns a report with
  `snapshot_captured_in_future`; it is not silently labeled current.
* The pure engine never refreshes data.
* When a repository has no snapshot, the budget service returns `None`; the
  CLI prints a clear no-snapshot result (and a stable JSON error object under
  `--json`) instead of inventing a report.

## 15. Provider-neutral report

`PoolBudgetAssessment` contains:

* pool ID/name and reset timestamp,
* actual, expected, delta, progress,
* remaining source, remaining, available, and today's budget,
* non-negative time until reset,
* state, pressure, timing source, and warnings.

`BudgetReport` contains:

* capture/evaluation times and snapshot age,
* reserve policy and staleness,
* all pool assessments in snapshot order,
* effective pressure and binding pool,
* report-level warnings.

Models are frozen Pydantic value objects. JSON output is the report model's
JSON representation and never includes account IDs, plan names, raw metadata,
RPC data, or credentials.

## 16. Configuration

`BudgetConfig` is provider-independent and validates:

* reserve in `[0, 1)`,
* strict threshold ordering,
* finite non-negative weekday weights with at least one positive value,
* a valid IANA timezone,
* positive stale threshold,
* pressure values in `[0, 1]` and non-decreasing order.

`BudgetConfig` and `WeekdayWeights` use strict field validation and forbid
unknown keys. String-to-number coercion, booleans supplied as integers, and
misspelled fields are rejected. A future YAML/environment loader must perform
any intentional conversion before constructing these core policy models.

Configuration loading/YAML merging is outside the mathematical engine and is
not required in Phase 4.

## 17. Errors

Ordinary missing or unknown provider data produces `UNKNOWN` fields/states.
Exceptions are reserved for invalid caller contracts:

* invalid `BudgetConfig` -> Pydantic `ValidationError`,
* naive evaluation time -> `BudgetEvaluationError`,
* duplicate pool IDs or another impossible snapshot invariant ->
  `BudgetEvaluationError`.

## 18. Service and CLI

`BudgetService` performs only:

```text
SnapshotRepository.get_latest_snapshot()
    -> BudgetEngine.evaluate(snapshot, now)
    -> BudgetReport | None
```

`quotapilot budget` reads the latest persisted snapshot. `--json` emits the
stable Pydantic report JSON. Human output renders unavailable values literally
as `unavailable`. Neither output makes routing recommendations.

## 19. Acceptance criteria

Phase 4 is complete when:

1. The engine is provider-independent and pure for fixed inputs.
2. Actual, expected, pace, reserve, states, daily allocation, and pressure
   follow this contract.
3. Missing/invalid timing produces conservative `UNKNOWN` results.
4. Reset-only pools do not fabricate a start.
5. Derived starts are marked `derived_window_seconds`.
6. Multi-window binding uses maximum known pressure and deterministic ties.
7. Stale/future snapshots are visible and never silently presented as live.
8. Human and JSON CLI outputs work without exposing private account data.
9. Save -> reload -> evaluate is semantically equivalent to direct evaluate.
10. Offline unit/integration tests cover all boundary cases in this contract.
11. Optional live capture -> persist -> evaluate remains explicitly gated.
12. No Phase 5 routing, scoring, effort, or escalation code exists.
13. Elapsed calculations are correct across DST folds/gaps and derived
    durations remain exact elapsed seconds.
14. Threshold neighbors follow the stated inequalities with no fuzzy band.
15. Daily allocation is O(1) in the number of remaining days.
