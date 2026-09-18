# QuotaPilot Phase 5.5 — Capability Metadata & Routing Calibration Contract

Status: Implemented
Phase: 5.5
Depends on:

- Phase 2 provider boundary
- Phase 3 persistence boundary
- Phase 4 Budget Engine
- Phase 5 quota-aware routing engine

---

## 1. Purpose

Phase 5.5 makes the Phase 5 routing engine practically usable against real model catalogs that do not directly expose all routing metadata required by QuotaPilot.

The current routing engine intentionally refuses to infer model strength, quota cost, or latency from model names.

Therefore Phase 5.5 introduces:

```text
CapabilitySet
+
Versioned Model Profile Registry
↓
Capability Enrichment
↓
Enriched CapabilitySet
↓
Existing Routing Engine
```

The phase also introduces deterministic calibration scenarios for evaluating whether routing policy behaves sensibly.

Phase 5.5 MUST NOT implement automatic model execution.

---

## 2. Goals

Phase 5.5 MUST support:

- versioned model profile files,
- strict profile validation,
- routing metadata provenance,
- metadata staleness handling,
- exact model-ID matching,
- capability enrichment,
- provider-truth precedence,
- unknown-model preservation,
- deterministic calibration scenarios,
- routing replay/evaluation,
- anti-waste validation,
- underpower protection validation,
- UNKNOWN-quota validation,
- live capability-enrichment integration where possible.

Phase 5.5 MUST NOT implement:

- automatic Codex invocation,
- automatic Claude Code invocation,
- automatic model switching,
- automatic retries,
- automatic escalation execution,
- remote profile auto-update,
- hidden telemetry,
- online learning,
- opaque automated policy optimization.

---

## 3. Core architecture

Canonical flow:

```text
Provider
   ↓
CapabilitySet
   ↓
Capability Enricher
   ↑
Model Profile Registry
   ↓
Enriched CapabilitySet
   ↓
Routing Engine
```

Calibration flow:

```text
Synthetic / anonymized Scenario
        ↓
TaskProfile
BudgetReport
Enriched CapabilitySet
RoutingPolicy
        ↓
Routing Engine
        ↓
RoutingRecommendation
        ↓
Calibration Evaluation
```

---

## 4. Architectural boundary

Model-specific knowledge belongs outside the routing core.

Forbidden inside routing logic:

```python
if "sol" in model.id:
    ...
```

```python
if model.id == "gpt-5.6-terra":
    ...
```

```python
if provider == "openai":
    power = ...
```

The routing engine must remain provider-independent.

---

## 5. Model profile location

Profiles live under:

```text
policies/model_profiles/
```

Initial OpenAI Codex profile:

```text
policies/model_profiles/openai_codex.yaml
```

Profiles are policy/configuration artifacts and MUST be Git-reviewable.

---

## 6. Profile schema

Profiles MUST use an explicit schema version.

Conceptual structure:

```yaml
schema_version: 1
provider: openai
product: codex
verified_at: 2026-09-18

models:
  some-model-id:
    relative_power: 0.80
    relative_cost: 0.50
    relative_latency: 0.30

    effort_order:
      - medium
      - high

    provenance:
      source: manual
      confidence: provisional
      evidence:
        - "Documented rationale"
```

The exact implementation MAY refine field structure, but MUST preserve:

- schema version,
- provider/product identity,
- verified timestamp,
- exact model ID,
- relative routing metrics,
- provenance,
- evidence,
- effort ordering when supplied.

Unknown keys MUST be rejected.

---

## 7. Relative metric semantics

### relative_power

```text
0.0 = weakest routable capability in the chosen reference scale
1.0 = strongest reference capability
```

This is a routing heuristic.

It MUST NOT be presented as an official provider score unless explicitly provider-sourced.

### relative_cost

```text
0.0 = lowest estimated constrained-resource / quota cost
1.0 = highest estimated constrained-resource / quota cost
```

This does NOT automatically mean API token price.

### relative_latency

Convention:

```text
0.0 = fastest
1.0 = slowest
```

All three metrics MUST satisfy:

```text
0.0 <= value <= 1.0
```

---

## 8. Provenance

Every manually or fallback supplied routing value MUST record provenance.

Supported conceptual sources:

```text
provider
benchmark
empirical
manual
fallback
unknown
```

Confidence SHOULD use a finite qualitative enum such as:

```text
high
medium
low
provisional
```

Do not expose fake probabilities.

Evidence MUST be human-reviewable.

---

## 9. Metadata precedence

Capability enrichment MUST use deterministic precedence.

Recommended hierarchy:

```text
1. provider-confirmed normalized metadata
2. local empirically calibrated metadata
3. versioned manually maintained profile
4. generic fallback profile
5. unknown / unroutable
```

Lower-precedence metadata MUST NOT overwrite higher-confidence provider truth.

The enrichment layer should normally fill missing values.

---

## 10. Model matching

Default matching is exact model-ID matching.

Loose substring matching is forbidden by default.

Unknown future model IDs MUST remain unknown.

Aliases MAY be supported only when explicitly declared and unambiguous.

---

## 11. Unknown models

Unknown models remain in `CapabilitySet`.

They MUST NOT crash enrichment.

If insufficient routing metadata exists, they remain unroutable.

The system MUST NOT assign invented `relative_power`, `relative_cost`, or `relative_latency` merely to avoid a no-route result.

Unknown is a valid state.

---

## 12. Staleness

Profiles MUST carry:

```text
verified_at
```

The schema MAY also support:

```text
expires_after_days
```

or an equivalent staleness policy.

Stale metadata MUST be visible.

The chosen default must be explicit and conservative.

---

## 13. Capability enrichment

Introduce a provider-independent enrichment abstraction.

Conceptually:

```python
class CapabilityEnricher:
    def enrich(
        self,
        capabilities: CapabilitySet,
        registry: ModelProfileRegistry,
    ) -> CapabilitySet:
        ...
```

Requirements:

- input `CapabilitySet` is not mutated,
- provider-supplied values are preserved,
- missing values may be filled,
- unknown models remain,
- provenance is attached,
- output is deterministic.

---

## 14. Profile registry

Suggested package:

```text
src/quotapilot/capabilities/
```

Possible structure:

```text
capabilities/
├── __init__.py
├── models.py
├── loader.py
├── registry.py
├── enrichment.py
└── errors.py
```

Registry responsibilities:

- load profile files,
- validate schema,
- index models,
- perform exact matching,
- expose provenance,
- detect stale metadata,
- support future providers.

---

## 15. Initial OpenAI Codex coverage

The initial profile MUST be based on model IDs actually discovered by the current Codex capability path.

Before profile creation:

1. inspect current `model/list` fixture or live catalog,
2. identify current model IDs,
3. identify supported effort catalogs,
4. separate provider-confirmed fields from manual routing metadata.

Do not invent model IDs.

Do not include account-specific information.

---

## 16. Initial metadata quality

Initial metric values are heuristic unless strong evidence exists.

Insufficient evidence SHOULD result in:

```text
confidence: low
```

or:

```text
confidence: provisional
```

or leaving the value unset.

Do not fill every metric merely to maximize routability.

A typed no-route result is preferable to unsupported certainty.

---

## 17. Cost semantics

`relative_cost` represents:

```text
estimated relative consumption pressure on the constrained subscription/quota system
```

It does not necessarily equal API price.

If exact model-specific quota cost is unknown, the profile MUST document the approximation.

---

## 18. Latency semantics

Latency metadata should describe coarse model tendency.

It should not attempt to encode temporary effects such as network congestion or queue delay.

Initial relative latency values MAY be coarse.

---

## 19. Effort metadata

Profiles MAY enrich effort ordering where provider-normalized capability data lacks order.

Example:

```yaml
effort_order:
  - low
  - medium
  - high
```

Effort order MUST be explicitly declared.

Do not sort arbitrary effort strings lexically.

---

## 20. Calibration dataset

Create a provider-independent calibration scenario representation.

Suggested location:

```text
calibration/
```

or:

```text
tests/calibration/
```

A scenario SHOULD contain:

```text
scenario_id
task_class
task profile dimensions
budget state / pressure
capability-profile version
acceptable models
unacceptable models
notes
```

Raw private task text is not required.

Prefer synthetic or anonymized scenarios.

---

## 21. Scenario suite

Initial scenario coverage MUST include at least:

1. trivial typo / mechanical edit
2. small deterministic refactor
3. normal bounded implementation
4. test-writing task
5. local debugging
6. complex debugging
7. repository-wide change
8. architecture decision
9. research/review task
10. high-failure-cost low-verifiability task

Scenarios SHOULD exercise several quota states:

```text
VERY_UNDER
ON_TRACK
OVER
CRITICAL
UNKNOWN
```

---

## 22. Expected outcome format

Calibration SHOULD avoid forcing one exact model when several answers are reasonable.

Prefer:

```text
acceptable_models
unacceptable_models
```

For high-risk tasks:

```text
unacceptable:
  - candidates below required capability floor
```

This reduces overfitting to arbitrary labels.

---

## 23. Replay evaluation

Provide a deterministic calibration replay mechanism.

Possible CLI:

```bash
quotapilot calibrate evaluate
```

A developer-only command/script is also acceptable.

Evaluation SHOULD report:

```text
scenario count
acceptable-set hits
unacceptable recommendations
capability-floor violations
anti-waste violations
UNKNOWN handling violations
monotonicity violations
```

Do not automatically tune coefficients in Phase 5.5.

---

## 24. Calibration metrics

Avoid relying only on one aggregate score.

Expose component metrics:

- acceptable recommendation rate,
- underpower violations,
- anti-waste violations,
- UNKNOWN quota failures,
- unsupported effort violations,
- non-selectable model violations.

An aggregate score MAY exist, but components remain visible.

---

## 25. Policy comparison

Phase 5.5 MAY support comparing multiple explicit policy configurations against the same scenario set.

No opaque optimizer.

Forbidden:

- reinforcement learning,
- gradient search,
- hidden auto-tuning,
- automatic mutation of production policy from small datasets.

Manual review remains required.

---

## 26. Real-task replay

QuotaPilot SHOULD support manual replay using explicit/anonymized task-profile values.

Existing explicit-routing support SHOULD be reused.

Do not duplicate equivalent interfaces.

---

## 27. Empirical feedback preparation

Future calibration may use:

```text
recommended model
actual model used
success/failure
escalated
user assessment
```

Phase 5.5 MAY define feedback-domain types.

It MUST NOT automatically capture private task content.

Any future persistence of task feedback must be opt-in.

---

## 28. Router integration

The existing Routing Engine remains conceptually unchanged.

```text
CapabilitySet
↓
CapabilityEnricher
↓
Enriched CapabilitySet
↓
RoutingEngine
```

Routing changes should only occur if calibration identifies a concrete routing defect.

---

## 29. Live integration

Important live path:

```text
live model/list
↓
CapabilitySet
↓
profile enrichment
↓
BudgetReport
↓
RoutingRecommendation
```

Guard authenticated integration with:

```text
QUOTAPILOT_INTEGRATION=1
```

Desired behavior:

```text
before enrichment:
no route if metadata insufficient

after enrichment:
valid route only for models covered by valid profile metadata
```

Unprofiled models remain unroutable when required metadata is absent.

---

## 30. Model profile inspection

Provide user/developer observability.

Possible commands:

```bash
quotapilot models
```

or:

```bash
quotapilot profiles show
```

Output should distinguish metadata source:

```text
provider
empirical
profile/manual
fallback
unknown
stale
```

Do not expose private account metadata.

---

## 31. Route explanation provenance

Routing output SHOULD expose profile provenance when enriched metadata materially affected selection.

Example:

```text
Capability metadata
Source: local-profile
Confidence: provisional
Verified: 2026-09-18
```

This prevents heuristic metadata from appearing provider-confirmed.

---

## 32. Profile update safety

Profiles materially affect recommendations.

Therefore:

- profile changes are explicit Git changes,
- profile schema is validated,
- provenance is human-readable,
- automatic remote updates are forbidden in Phase 5.5,
- unknown schema versions fail safely.

---

## 33. Privacy

Profiles may contain:

- public model IDs,
- routing metrics,
- public evidence,
- calibration rationale.

Profiles MUST NOT contain:

- account ID,
- email,
- session IDs,
- credentials,
- access tokens,
- private prompts,
- live usage history.

Calibration scenarios SHOULD be synthetic/anonymized.

---

## 34. Security

YAML/profile loading MUST NOT execute arbitrary code.

Use safe YAML parsing.

Reject malformed schema.

Do not accept arbitrary Python import paths or executable hooks in profiles.

---

## 35. Determinism

For identical:

```text
CapabilitySet
Model Profile Registry
RoutingPolicy
TaskProfile
BudgetReport
```

the enrichment and routing result MUST be identical.

No random calibration.

No implicit current network calls in the pure enrichment path.

---

## 36. Test requirements

### Profile loading

Test:

- valid profile,
- malformed YAML,
- invalid schema version,
- unknown keys,
- metric below 0,
- metric above 1,
- missing provenance,
- invalid confidence,
- invalid `verified_at`.

### Matching

Test:

- exact ID match,
- unknown model,
- explicit alias if implemented,
- ambiguous alias rejected.

### Enrichment

Test:

- missing metrics filled,
- provider values preserved,
- original `CapabilitySet` unchanged,
- unknown model retained,
- provenance preserved,
- effort order enrichment.

### Staleness

Test:

- fresh profile,
- stale profile,
- future `verified_at`,
- missing timestamp.

### Routing integration

Test:

- metadata-starved model no-route before enrichment,
- valid route after profile enrichment,
- unknown model remains unroutable.

---

## 37. Calibration test requirements

Scenario evaluation MUST detect:

- strongest-model waste on trivial task,
- underpowered recommendation on high-risk task,
- capability-floor violation caused by quota pressure,
- UNKNOWN quota treated as free,
- non-selectable model recommendation,
- unsupported effort recommendation.

Replay must be deterministic.

---

## 38. Acceptance criteria

Phase 5.5 is complete when:

1. `PHASE5_5_CALIBRATION_CONTRACT.md` exists and is normative.
2. Strict profile schema exists.
3. Profile versioning exists.
4. Profile provenance exists.
5. Staleness is represented.
6. Exact model-ID matching works.
7. Capability enrichment works.
8. Provider truth overrides fallback profile metadata.
9. Unknown models remain preserved.
10. Router contains no model-name-specific logic.
11. Initial OpenAI Codex profile coverage is documented.
12. Calibration scenario suite exists.
13. Anti-waste evaluation works.
14. Capability-floor evaluation works.
15. UNKNOWN quota evaluation works.
16. Replay is deterministic.
17. Live profile-enrichment path works where valid metadata exists.
18. Private account/task data is not introduced.
19. Offline tests pass.
20. Ruff passes.
21. Pyright passes.
22. Git working tree is clean after commit/push.
23. Phase 6 automatic execution is not implemented.

---

## 39. Completion boundary

At the end of Phase 5.5:

```text
Live capabilities
       +
Versioned profile metadata
       ↓
Enriched capabilities
       +
BudgetReport
       +
TaskProfile
       ↓
RoutingRecommendation
       ↓
Calibration evaluation
```

The output is a usable, explainable recommendation.

Phase 6 may later consume this recommendation for controlled execution.

Phase 5.5 itself remains recommendation-only.

---

## 40. Implemented profile policy

Profile schema version 1 is strict and rejects unknown keys, coercible numeric
values, invalid enums, malformed dates, and entries without human-readable
provenance. YAML is loaded only with `yaml.safe_load`. Registry matching uses
the provider identity plus the complete model ID; aliases and family guessing
are not implemented.

Precedence is provider-confirmed capability data, then empirical, benchmark,
manual, fallback, and unknown profile sources. Existing normalized capability
values are never overwritten. Equal-precedence definitions for the same exact
provider/model pair are rejected as ambiguous. Lower-precedence fresh entries
may fill fields that a higher-precedence entry leaves absent.

Freshness is evaluated against an explicit date. A profile is `fresh` from
`verified_at` through `verified_at + expires_after_days`, inclusive. It is
`stale` after that date, and `unknown` when evaluated before `verified_at` or
when no expiry policy exists. Only fresh profile fields are applied; stale or
unknown-freshness matches remain visible with provenance and warnings but do
not make a model routable.

The shipped OpenAI Codex profile is intentionally partial. It exactly covers
the six IDs observed in the sanitized and live `model/list` catalogs on
2026-09-18. It supplies explicit effort order for those exact catalogs,
provisional power for `gpt-6-astra` and `gpt-5.6-luna`, and provisional
cost/latency only for `gpt-5.6-luna`. The other four models remain unroutable
until defensible power metadata exists. These values are local manual policy,
not provider-confirmed scores.

The root policy and scenario files are Git-reviewable and are also bundled in
the wheel under `quotapilot/_data`; source-tree paths remain the development
fallback.

## 41. Implemented calibration policy

`calibration/scenarios.yaml` contains ten synthetic cases spanning mechanical
work, refactoring, implementation, tests, debugging, repository-wide work,
architecture, review, and high-risk low-verifiability work. The deterministic
evaluator invokes the existing Routing Engine twice and reports component
metrics rather than optimizing coefficients or rewriting policy.

The initial suite result is 10 acceptable hits from 10 scenarios, with zero
unacceptable, capability-floor, anti-waste, UNKNOWN-quota, unsupported-effort,
non-selectable-model, determinism, or no-recommendation violations. This is a
regression baseline, not empirical evidence that the policy is optimal.
