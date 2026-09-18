# QuotaPilot Development Handoff

> Shared current-state window for Claude Code and Codex. Read the technical
> design, phase contracts, and decision log before continuing.

## Current state

- Date: 2026-09-18
- Last agent: Codex
- Current phase: **Phase 5 quota-aware advisory routing complete**
- Phase 2 provider boundary: **COMPLETE**
- Phase 3/3.1 persistence boundary: **COMPLETE**
- Phase 4/4.1 budget boundary: **COMPLETE**
- Phase 5 routing boundary: **COMPLETE**
- Phase 6 automatic/controlled execution: **NOT IMPLEMENTED**
- Phase 6 readiness: **READY**, with calibration limitations below
- Dependency direction remains:
  `CLI -> Services -> Budget / Routing -> Domain`, `Persistence -> Domain`,
  `Providers -> Domain`

The normative routing contract is `docs/PHASE5_ROUTING_CONTRACT.md`.

## Phase 5 implementation

### Task profile and policy

- `TaskProfile`, `TaskClass`, and `TaskProfileOverrides` are strict,
  provider-neutral models with bounded dimensions and explicit
  `heuristic`/`mixed`/`explicit` provenance.
- `TaskProfiler` uses a small deterministic keyword table and fixed class
  profiles; no LLM, clock, environment, or provider call is involved.
- `RoutingPolicy` is strict/frozen, rejects unknown keys and coercion, and
  centralizes scoring, fallback, effort, escalation, and alternatives policy.

### Required power and candidate scoring

- Difficulty uses the contract's 30/20/20/15/15 formula. Required power adds
  0.10 each for failure cost and low verifiability.
- A risk-tightened capability floor excludes severe underpowering before cost
  can influence the winner. `CRITICAL + hard/high-risk` therefore still uses
  a sufficient model when one exists.
- Eligible utility exposes quality, quota, latency, and over-capability
  components independently. Selection ties are utility, effective cost,
  effective latency, then model ID.
- `VERY_UNDER + trivial` favors adequate lightweight capability rather than
  the strongest model.
- Unknown quota uses the configurable neutral fallback (default 0.50), remains
  labeled `fallback_unknown`, and emits a warning.

### Capability metadata and effort

- Non-selectable models and models without valid relative power remain visible
  in candidate scores but cannot be selected. Power is never inferred from a
  model ID.
- Missing cost/latency uses a visible neutral fallback (default 0.50), never
  zero.
- `AIModel.effort_order` is the explicit normalized least-to-greatest order and
  must exactly match the supported catalog. Unordered effort strings are
  preserved but produce no effort recommendation.
- Quota pressure can reduce effort only for low-risk, low-ambiguity,
  high-verifiability work. High-risk work resists reduction.

### Escalation, alternatives, and output

- Escalation is advisory and monotonic: higher effort and/or the next stronger
  eligible model. It contains no duplicates, unsupported efforts, weaker
  fallback, or execution behavior.
- Alternatives are bounded and drawn only from known selectable eligible
  models.
- Deterministic explanations include difficulty, risk, quota effect,
  capability floor, weaker/stronger tradeoffs, effort, and escalation.
- `quotapilot route "..."` and `--json` use the latest persisted snapshot via
  `RoutingService`. Expected no-snapshot/no-route states are clean errors.
- Route JSON contains routing-domain information and the user-supplied task,
  but no account ID, plan, raw observations, credentials, or hidden capability
  metadata. Task text is not persisted.

## Verification

Commands run from the repository root:

```bash
uv run pytest
uv run ruff check .
uv run pyright
uv run quotapilot --help
uv run quotapilot route --help
QUOTAPILOT_INTEGRATION=1 uv run pytest tests/integration/
```

Results:

- Offline/default pytest: **309 passed, 5 skipped**. The five skips are the
  explicitly gated authenticated integration suite.
- Ruff: **All checks passed**.
- Pyright: **0 errors, 0 warnings, 0 informations**.
- Root and route CLI help: **PASS**.
- Live integration: **5 passed**. Capture -> temporary SQLite -> BudgetReport
  remains successful. Current live Codex models lack explicit QuotaPilot
  relative routing metadata, so the test verifies a typed no-route result
  rather than inventing model power.

Normal CI remains offline and credential-free.

## Privacy/security state

- Phase 3.1 account pseudonymization and provider sanitization are unchanged.
- Routing imports no OpenAI/Codex implementation or SQLite implementation.
- The pure engine performs no I/O and no automatic execution.
- No prompt/task storage, credentials, raw account identity, live telemetry,
  provider cookies, or generated caches were added to tracked content.

## Remaining risks / deferred decisions

- Routing coefficients and class profiles are deterministic heuristics, not
  empirically calibrated measurements of model performance.
- Current Codex `model/list` data does not provide normalized relative
  power/cost/latency or verified effort order. A future external capability
  definition/calibration layer is required before live models become routable;
  it must not infer tiers from IDs.
- Missing cost/latency intentionally uses a neutral fallback, lowering
  recommendation confidence.
- Task profiling is deliberately small and keyword-based; explicit overrides
  are the precision mechanism in Phase 5.
- Long-lived versus ephemeral Codex app-server lifecycle remains deferred.

## Next task

Phase 6 may design controlled execution/integration around the advisory
`RoutingRecommendation`. It must not treat a recommendation as authorization,
must require explicit trustworthy capability metadata, and must preserve the
no-hidden-task-persistence and provider-independence boundaries.
