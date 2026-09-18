# QuotaPilot Development Handoff

> Shared current-state window for Claude Code and Codex. Read the technical
> design, phase contracts, and decision log before continuing.

## Current state

- Date: 2026-09-18
- Last agent: Codex
- Current phase: **Phase 5.5 capability metadata and calibration complete**
- Phase 2 provider boundary: **COMPLETE**
- Phase 3/3.1 persistence boundary: **COMPLETE**
- Phase 4/4.1 budget boundary: **COMPLETE**
- Phase 5 routing boundary: **COMPLETE**
- Phase 5.5 enrichment/calibration boundary: **COMPLETE**
- Phase 6 automatic/controlled execution: **NOT IMPLEMENTED**
- Phase 6 readiness: **READY**, subject to the limitations below
- Dependency direction remains:
  `CLI -> Services -> Budget / Routing -> Domain`, `Persistence -> Domain`,
  `Providers -> Domain`; capability enrichment sits before Routing and imports
  no provider implementation.

The normative Phase 5.5 contract is
`docs/PHASE5_5_CALIBRATION_CONTRACT.md`.

## Phase 5.5 implementation

### Capability profiles

- `src/quotapilot/capabilities/` provides strict schema models, safe YAML
  loading, an exact-ID registry, deterministic enrichment, typed errors, and
  privacy-safe model views.
- Schema version 1 rejects unknown keys, unsupported versions, malformed
  dates, numeric coercion, invalid metric ranges/enums, missing provenance,
  and ambiguous same-precedence definitions.
- Matching is provider plus exact model ID. No alias, prefix, substring,
  version, family, or model-name inference exists.
- Existing normalized capability fields win. Fresh empirical, benchmark,
  manual, fallback, and unknown profile entries may fill only missing fields
  in that order. Unknown models stay present and unroutable.
- Freshness uses an injected evaluation date. Only entries within the
  inclusive verification/expiry interval apply. Stale, future-dated, and
  missing-expiry entries remain visible with provenance and warnings but are
  non-operative.
- Repeated enrichment preserves profile provenance instead of relabeling a
  previously supplied field as provider-confirmed.

### Initial Codex profile coverage

- `policies/model_profiles/openai_codex.yaml` covers only the six exact IDs in
  the sanitized and live 2026-09-18 catalogs: `gpt-6-astra`, `gpt-5.6-sol`,
  `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-daybreak-blue-latest`, and `gpt-5.5`.
- All six receive an explicit effort order matching the observed catalogs.
- Only Astra and Luna receive provisional relative power. Only Luna receives
  provisional cost and latency. The other four deliberately remain
  unroutable until defensible power evidence exists.
- Every supplied value is marked manual/provisional with human-readable
  evidence. None is represented as an official provider score.
- The root profile/scenario files remain Git-reviewable and are also included
  as wheel data for installed CLI use.

### Calibration

- `src/quotapilot/calibration/` and `calibration/scenarios.yaml` provide a
  strict, deterministic replay layer over the existing Routing Engine.
- Ten synthetic scenarios cover typo, refactor, bounded implementation,
  test-writing, local and complex debugging, repository-wide change,
  architecture, research/review, and high-risk low-verifiability work across
  VERY_UNDER, ON_TRACK, OVER, CRITICAL, and UNKNOWN quota.
- Initial result: **10/10 acceptable hits** and zero unacceptable,
  capability-floor, anti-waste, UNKNOWN-quota, unsupported-effort,
  non-selectable-model, determinism, or routing-failure violations.
- The evaluator reports component metrics only. It does not optimize policy,
  mutate profiles, use an LLM/network, or execute a recommendation.

### Service and CLI

- `RoutingService` optionally enriches the latest persisted CapabilitySet
  before invoking the unchanged pure router. Material local-profile use is
  exposed in deterministic explanations/warnings and lowers confidence for
  low/provisional metadata.
- `quotapilot route` enables the shipped profile registry by default and
  accepts `--profile-dir` for explicit alternatives.
- `quotapilot models [--json] [--as-of DATE]` exposes only routing-relevant
  capability/profile data, including routability, provenance, confidence, and
  freshness. It does not fetch live data or expose account fields.
- `quotapilot calibrate evaluate [--json]` reports the scenario outcomes and
  component violation metrics.

## Verification

Commands run from the repository root:

```bash
uv run pytest
uv run ruff check .
uv run pyright
uv run quotapilot --help
uv run quotapilot route --help
uv run quotapilot models --help
uv run quotapilot calibrate evaluate --help
QUOTAPILOT_INTEGRATION=1 uv run pytest tests/integration/
```

Results:

- Offline/default pytest: **347 passed, 5 skipped**. The five skips are the
  explicitly gated authenticated live tests.
- Live integration: **5 passed**. It verifies live catalog -> persistence ->
  budget -> exact profile enrichment -> route where fresh exact metadata is
  available; unmatched models remain safely unroutable.
- Ruff: **All checks passed**.
- Pyright: **0 errors, 0 warnings, 0 informations**.
- Root, route, models, and calibration CLI help commands: **PASS**.

Normal CI remains offline and credential-free.

## Privacy/security state

- Profile and calibration YAML use `yaml.safe_load` plus strict Pydantic
  validation; no executable YAML/Python hooks are accepted.
- No prompt history, raw account identity, credential, token, session ID,
  private task/source text, or live usage telemetry was added.
- Model inspection is a safe projection and does not expose account, plan, or
  raw snapshot metadata.
- The pure enrichment/calibration paths perform no network, SQLite, provider,
  environment, or execution operation.
- Phase 6 execution behavior does not exist.

## Remaining risks / deferred decisions

- Numeric profile values and routing coefficients are provisional heuristics,
  not empirically calibrated measurements. The ten-scenario suite is a
  regression baseline, not evidence of optimal model choice.
- Only two current Codex models have provisional power values; four remain
  unroutable by design. Exact future IDs receive no inherited metadata.
- Profile freshness requires human review and a Git update before expiry.
- Effort ordering is local policy based on the observed provider catalog; it
  is not represented as provider-confirmed ranking metadata.
- Long-lived versus ephemeral Codex app-server lifecycle remains deferred.

## Next task

Phase 6 may design a controlled integration around advisory
`RoutingRecommendation` values. It must treat profile provenance/confidence as
policy evidence rather than provider truth, require explicit authorization for
execution, preserve exact capability matching, and keep task persistence and
automatic escalation out unless separately designed and approved.
