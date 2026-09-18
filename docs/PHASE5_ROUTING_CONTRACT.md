
# QuotaPilot Phase 5 — Routing Contract

Status: Implemented

This document is the normative Phase 5 contract. The implementation-specific
rules in section 41 resolve the choices intentionally left open below.

Repository:

```text
/home/hira/main/projects/tools/QuotaPilot
```

Current state:

* Provider boundary: COMPLETE
* Persistence boundary: COMPLETE
* Budget Engine / Phase 4.1: COMPLETE
* Phase 5: IMPLEMENTED
* GitHub main: clean and synchronized
* BudgetReport is now trustworthy for routing input

Your task is to design, implement, test, document, commit, and push:

# Phase 5 — Quota-aware Model & Effort Routing

Do NOT implement automatic model execution.

---

## 0. Read first

Read completely:

1. `docs/TECHNICAL_DESIGN.md`
2. `docs/PHASE3_PERSISTENCE_CONTRACT.md`
3. `docs/PHASE4_BUDGET_CONTRACT.md`
4. `docs/PHASE5_ROUTING_CONTRACT.md`
5. `docs/DECISIONS.md`
6. `docs/HANDOFF.md`
7. `docs/lessons.md` if present
8. `AGENTS.md`

Then inspect:

```text
src/quotapilot/domain/
src/quotapilot/budget/
src/quotapilot/services/
src/quotapilot/history/
src/quotapilot/providers/
src/quotapilot/cli/
tests/
pyproject.toml
```

Also inspect:

```bash
git status
git log --oneline --decorate -8
```

Do not rely on chat history instead of repository state.

---

# 1. Contract first

If `docs/PHASE5_ROUTING_CONTRACT.md` is not yet present, create it from the supplied Phase 5 contract before writing implementation code.

Treat it as the canonical Phase 5 specification.

If implementation reality requires a durable deviation:

* document it in `docs/DECISIONS.md`,
* update the contract explicitly,
* do not silently diverge.

---

# 2. Core goal

Implement:

```text
TaskProfile
+
BudgetReport
+
CapabilitySet
+
RoutingPolicy
↓
RoutingRecommendation
```

The output must include:

* recommended model,
* recommended effort when supported,
* explanation,
* candidate scoring,
* escalation path,
* alternatives,
* warnings.

Phase 5 is recommendation-only.

---

# 3. Strict scope

Do NOT implement:

* automatic Codex delegation,
* automatic Claude Code invocation,
* automatic model switching,
* automatic retries,
* actual escalation execution,
* task-history learning,
* online ML,
* background monitoring.

Do not modify provider quota semantics.

Do not modify Budget Engine math unless a genuine dependency defect is discovered.

---

# 4. Provider independence

Create a provider-independent routing package.

Suggested:

```text
src/quotapilot/routing/
├── __init__.py
├── models.py
├── profiler.py
├── scoring.py
├── effort.py
├── escalation.py
├── engine.py
└── errors.py
```

Simplify if appropriate.

Routing may depend on:

```text
domain
budget result models
```

Routing MUST NOT import:

```text
providers.openai_codex
history.sqlite
```

No:

```python
if plan == "pro"
```

No:

```python
if model.id == "gpt-5.6-sol"
```

No substring-based model tier inference.

---

# 5. Implement TaskProfile

Implement strict provider-independent models for:

```text
summary
task_class
complexity
ambiguity
failure_cost
verifiability
context_demand
latency_sensitivity
tags
profile_source
```

Numeric dimensions must strictly satisfy:

```text
0.0 <= x <= 1.0
```

Reject malformed coercion where appropriate.

Use `extra="forbid"` for policy/input structures where silent typos would be harmful.

---

# 6. Deterministic TaskProfiler

Implement a deterministic initial profiler.

Do not call an LLM.

It should support:

## Explicit dimensions

CLI/user supplied values override heuristics.

## Heuristic dimensions

Use conservative deterministic rules.

Keep the rules simple and inspectable.

Do not attempt NLP sophistication.

Examples of useful signals may include explicit words such as:

```text
typo
rename
format
test
debug
race
architecture
repository-wide
research
review
```

But avoid brittle provider/model keywords.

Expose:

```text
profile_source = explicit | heuristic | mixed
```

Add tests.

---

# 7. Difficulty calculation

Implement the Phase 5 contract's documented formula or an explicitly documented improvement.

Recommended initial baseline:

```text
D =
0.30 * complexity
+ 0.20 * ambiguity
+ 0.20 * failure_cost
+ 0.15 * (1 - verifiability)
+ 0.15 * context_demand
```

Strictly clamp only mathematically expected floating noise if necessary.

Do not create undocumented fuzzy threshold bands.

---

# 8. Candidate model preparation

Use discovered `CapabilitySet.models`.

Consider only models that are:

```text
selectable == True
```

for normal recommendation.

Do not infer capability from model names.

A model lacking sufficient routing metadata must be handled explicitly.

Recommended behavior for missing `relative_power`:

```text
not routable
```

with explanation/warning.

Do not invent a power score in the routing engine.

---

# 9. Required power

Derive required model capability from task characteristics.

Ensure:

```text
0 <= required_power <= 1
```

Failure cost and low verifiability should be capable of increasing the minimum required capability.

Document the actual formula in code/tests/decisions.

Keep it deterministic.

---

# 10. Candidate scoring

Implement independently inspectable components such as:

```text
quality score
quota penalty
latency penalty
over-capability/efficiency penalty if used
final utility
```

Do not expose only a black-box utility.

Budget pressure must influence quota penalty.

Model capability fit must remain the dominant safety constraint when underpowered.

---

# 11. Underpower guard

Implement a minimum capability floor.

High quota pressure must not route a difficult/high-risk task to an obviously inadequate model.

Add explicit tests for:

```text
CRITICAL quota
+
high-complexity/high-failure-cost task
```

Strong-enough model must still be selected if available.

---

# 12. Anti-waste behavior

Add the inverse invariant.

```text
VERY_UNDER quota
+
trivial mechanical task
```

must not automatically choose the strongest model.

This project exists to optimize value, not maximize model strength or minimize usage blindly.

Test it explicitly.

---

# 13. UNKNOWN Budget pressure

If:

```text
BudgetReport.effective_pressure is None
```

use documented neutral fallback pressure from policy.

Recommended default:

```text
0.50
```

Mark:

```text
quota_pressure_source = fallback_unknown
```

Add warning/explanation.

Do not treat UNKNOWN as free quota.

Do not treat UNKNOWN as exhaustion.

---

# 14. RoutingPolicy

Implement strict configuration.

At minimum:

```text
quota_pressure_weight
latency_weight
underpower_tolerance
unknown_quota_pressure
escalation_enabled
```

If named presets are implemented:

```text
balanced
conservative
aggressive
```

make them factories/config values, not scattered conditional logic.

Reject unknown/typo policy keys.

---

# 15. Deterministic model selection

Choose the highest eligible utility.

Define deterministic tie-breaks.

Recommended:

```text
utility DESC
relative_cost ASC
relative_latency ASC
model_id ASC
```

Test exact ties.

---

# 16. Effort recommendation

Recommend only effort values actually supported by the selected model.

Do not assume all models expose identical efforts.

Implement an effort-demand calculation based primarily on:

```text
complexity
ambiguity
failure_cost
1 - verifiability
```

Quota may influence effort conservatively.

Do not reduce effort aggressively for high-risk, low-verifiability tasks merely to save quota.

---

# 17. Effort ordering

Inspect how current capability normalization represents effort order.

If provider data has an explicit order, use normalized capability order.

If no order exists, introduce provider-independent normalized effort-rank metadata at the appropriate capability layer.

Do NOT hardcode model names.

If effort names require fallback order, document it centrally and explicitly.

Do not silently assume arbitrary strings are ordered.

---

# 18. Escalation path

Generate advisory escalation steps.

Build them from actual capabilities.

Preferred general logic:

```text
initial recommendation
↓
higher effort on same model, if meaningful
↓
next stronger routable model
↓
higher effort there
```

But avoid pointless steps.

Examples:

* no duplicate consecutive step,
* do not lower capability during escalation,
* strongest/highest-effort case may have empty escalation path.

Do not execute escalation.

---

# 19. Alternatives

Return at most a small useful set.

Suggested maximum:

```text
3
```

Try to include:

* cheaper acceptable alternative,
* stronger fallback,

when such candidates exist.

Do not flood normal CLI output with all candidates.

---

# 20. Explanation generation

Generate deterministic explanations.

Every recommendation should explain:

```text
task difficulty
task risk/verifiability
quota pressure
model capability fit
cost/latency tradeoff
effort choice
escalation
```

Do not use an LLM for explanations.

---

# 21. RoutingRecommendation

Implement a stable Pydantic result model.

Include sufficient fields for future automation.

At minimum:

```text
selected_model_id
selected_effort
required_power
quota_pressure
quota_pressure_source
task_profile
candidate_scores
escalation_path
alternatives
explanation
warnings
```

Candidate scoring should expose the major score components.

---

# 22. Routing service

Introduce a service/composition layer if appropriate.

Conceptually:

```text
latest snapshot
    ↓
BudgetEngine
    ↓
BudgetReport

task text
    ↓
TaskProfiler
    ↓
TaskProfile

capabilities
    ↓

RoutingEngine
    ↓
RoutingRecommendation
```

Do not put DB/provider I/O inside the pure RoutingEngine.

---

# 23. CLI

Implement:

```bash
quotapilot route "Fix typo in README"
```

and:

```bash
quotapilot route "..." --json
```

Useful optional flags:

```text
--complexity
--ambiguity
--failure-cost
--verifiability
--context-demand
--latency-sensitivity
```

Do not require manual profiling for normal usage.

---

# 24. CLI behavior when data is unavailable

Handle cleanly:

* no persisted snapshot,
* no routable model,
* UNKNOWN budget pressure,
* no effort catalog,
* stale budget.

Do not show Python tracebacks for ordinary user-state problems.

Use clear typed/application errors.

---

# 25. Privacy

Do not persist task prompts automatically.

Do not expose:

* account ID,
* raw provider observation,
* credentials,
* hidden metadata,

in normal route output.

JSON should contain routing-domain information only.

---

# 26. Core test cases

At minimum implement:

## Mechanical

```text
Fix typo in README
```

Expected tendency:

lightweight adequate model.

## Normal coding

Local bounded implementation.

Expected tendency:

mid capability depending on candidate set.

## Complex debugging

High complexity/context.

Expected tendency:

stronger capability.

## Architecture

High ambiguity, high failure cost, low verifiability.

Must not be routed to severely underpowered model under quota pressure.

## Review

High verifiability may permit efficient model.

---

# 27. Budget-state test matrix

Test routing under:

```text
VERY_UNDER
UNDER
ON_TRACK
OVER
CRITICAL
UNKNOWN
```

Same task should respond sensibly to pressure changes without violating capability floor.

---

# 28. Candidate-set tests

Test:

* one model,
* two models,
* many models,
* all models non-selectable,
* missing relative_power,
* missing relative_cost,
* missing relative_latency,
* exact utility tie,
* unknown new model.

No candidate condition must fail cleanly.

---

# 29. Effort tests

Test:

* no efforts,
* one effort,
* several efforts,
* low-demand task,
* high-demand task,
* high quota pressure,
* high failure cost under high pressure,
* unknown effort names/order handling.

Selected effort must always belong to selected model's supported effort set.

---

# 30. Escalation tests

Test:

* increase effort same model,
* move stronger model,
* skip useless escalation,
* strongest model selected,
* escalation disabled,
* no effort catalog,
* no duplicate consecutive steps.

---

# 31. Monotonicity/invariant tests

Test important invariants.

For otherwise identical inputs:

```text
higher complexity
should not systematically choose weaker capability

higher failure cost
should not reduce required capability

higher verifiability
may permit cheaper model

higher quota pressure
may lower cost
but must respect capability floor
```

Also:

```text
VERY_UNDER + trivial task
must not imply strongest model
```

---

# 32. Determinism

Exactly equal:

```text
TaskProfile
BudgetReport
CapabilitySet
RoutingPolicy
```

must always produce exactly equal recommendation.

No time/random/global-state dependence in the core engine.

---

# 33. Integration tests

Test:

```text
persisted snapshot
↓
BudgetReport
↓
RoutingRecommendation
```

using provider-independent fixtures.

Also optionally:

```text
live capture
↓
persist
↓
budget
↓
route
```

behind:

```text
QUOTAPILOT_INTEGRATION=1
```

If live capabilities lack routing metadata, do not invent it merely to make integration pass.

Report that explicitly.

---

# 34. No Phase 6 execution

Do NOT:

* launch Codex models,
* edit Codex config automatically,
* delegate to subagents,
* retry tasks automatically,
* execute escalation path.

Phase 5 is advisory.

---

# 35. Documentation

Create/update:

```text
docs/PHASE5_ROUTING_CONTRACT.md
docs/TECHNICAL_DESIGN.md
docs/DECISIONS.md
docs/HANDOFF.md
docs/lessons.md
```

Document:

* scoring formula,
* capability floor,
* UNKNOWN pressure,
* effort logic,
* escalation strategy,
* model metadata assumptions,
* calibration limitations.

Explicitly state that initial routing coefficients are heuristic and not empirically calibrated.

---

# 36. Verification

Run:

```bash
uv run pytest
uv run ruff check .
uv run pyright
uv run quotapilot --help
uv run quotapilot route --help
```

If safe and applicable:

```bash
QUOTAPILOT_INTEGRATION=1 uv run pytest tests/integration/
```

---

# 37. Security/privacy review

Before committing, inspect for:

* credentials,
* raw account identity,
* raw provider telemetry,
* persisted task text,
* accidental caches,
* generated artifacts.

Verify routing does not expose unnecessary private metadata.

---

# 38. Git

After all acceptance criteria pass:

```bash
git status
git diff
```

Create one coherent commit.

Suggested:

```text
feat: add quota-aware model router
```

Push normally:

```bash
git push origin main
```

No force push.

Verify local/remote HEAD equality.

---

# 39. Acceptance gate

Do not claim Phase 5 complete unless:

```text
Phase 5 contract: COMPLETE

TaskProfile: PASS
TaskProfiler: PASS
RoutingPolicy: PASS
Required power: PASS
Candidate scoring: PASS
Capability floor: PASS
Quota-aware scoring: PASS

VERY_UNDER anti-waste behavior: PASS
CRITICAL quota capability-floor behavior: PASS
UNKNOWN quota handling: PASS

Effort recommendation: PASS
Escalation path: PASS
Alternatives: PASS
Explainability: PASS

Provider independence: PASS
Determinism: PASS
Monotonicity tests: PASS

CLI route: PASS
JSON route: PASS

Offline tests: PASS
Ruff: PASS
Pyright: PASS

Live integration:
PASS or limitation explicitly documented

Privacy review: PASS

Git working tree after commit: CLEAN
Push: SUCCESS

Phase 6 execution: NOT IMPLEMENTED
```

---

# 40. Final response

Report:

1. Phase 5 contract
2. TaskProfile/profiler
3. routing formula
4. model capability handling
5. quota-pressure behavior
6. capability floor
7. effort logic
8. escalation logic
9. alternatives/explanations
10. CLI/JSON
11. test results
12. live integration
13. commit hash/message
14. push result
15. remaining risks/calibration limitations
16. exact final line:

```text
Phase 6 readiness: READY
```

or:

```text
Phase 6 readiness: NOT READY
```

Do not implement Phase 6.

---

# 41. Normative implementation choices

These rules are part of the contract, not provider facts. The coefficients are
deterministic and explainable, but are not yet empirically calibrated.

## Task profiling and difficulty

The heuristic profiler uses a small ordered keyword table to choose a task
class, then applies a fixed class profile. Explicit fields replace only the
corresponding heuristic fields. Provenance is `heuristic` with no overrides,
`mixed` with a partial override, and `explicit` only when all six dimensions
and the task class are supplied.

Difficulty is:

```text
D =
  0.30 * complexity
+ 0.20 * ambiguity
+ 0.20 * failure_cost
+ 0.15 * (1 - verifiability)
+ 0.15 * context_demand
```

Required power is:

```text
required_power = clamp(
    D
    + 0.10 * failure_cost
    + 0.10 * (1 - verifiability),
    0,
    1,
)
```

The capability floor tightens with risk:

```text
risk = (failure_cost + ambiguity + (1 - verifiability)) / 3
tolerance = max(0, underpower_tolerance - risk_tolerance_reduction * risk)
capability_floor = max(0, required_power - tolerance)
```

Defaults are `underpower_tolerance=0.15` and
`risk_tolerance_reduction=0.10`. A model below the floor is ineligible rather
than merely receiving a cost-sensitive score penalty.

## Candidate score and missing metadata

Only selectable models with a valid `[0, 1]` relative power are routable.
Unknown power is never invented. Missing/invalid cost or latency uses the
policy's explicit neutral fallback (default `0.50`) and is surfaced in both
the candidate source field and warnings.

For eligible models:

```text
quality_score =
    1 - 2.00 * (required_power - power)  when power < required_power
    1 - 0.35 * (power - required_power)  otherwise

quota_penalty = pressure * effective_cost * quota_pressure_weight
latency_penalty = latency_sensitivity * effective_latency * latency_weight
overcapability_penalty =
    max(0, power - required_power) * overcapability_weight

utility = quality_score
        - quota_penalty
        - latency_penalty
        - overcapability_penalty
```

Quality is bounded to `[0, 1]`. Default weights are `0.35` quota, `0.20`
latency, and `0.15` over-capability. Unknown quota uses policy fallback `0.50`
and remains labeled `fallback_unknown`. Selection ties are utility descending,
effective cost ascending, effective latency ascending, then model ID ascending.

## Effort, escalation, and alternatives

`AIModel.effort_order` is the provider-independent normalized ordering from
least to greatest reasoning effort. It must contain every supported effort
exactly once. `supported_efforts` without this explicit order is preserved,
but routing recommends no effort and emits a warning; it never sorts arbitrary
effort names.

Effort demand is:

```text
0.35 * complexity
+ 0.25 * ambiguity
+ 0.20 * failure_cost
+ 0.20 * (1 - verifiability)
```

It maps monotonically onto the ordered catalog. Pressure may reduce demand
only at pressure `>= 0.70` when failure cost and ambiguity are below `0.50`
and verifiability is at least `0.70`.

Escalation is advisory only. It raises effort on the selected model when
useful, then moves to the next stronger eligible model and may raise effort
there. When the initial model is below required power (but still above the
floor), the stronger model comes first. Steps never move back to a weaker
model and never execute. Alternatives contain at most the configured small
limit (default three), favoring a cheaper eligible option and a stronger
fallback before filling by ranked utility.

## Data, privacy, and live capability limitation

The pure engine consumes only `TaskProfile`, `BudgetReport`, `CapabilitySet`,
and `RoutingPolicy`. It performs no provider, SQLite, environment, clock, or
LLM access. The service loads the latest snapshot and computes its budget;
task text is returned to the caller but is not persisted. Route JSON excludes
account identity, plan data, raw observations, and capability metadata.

Current Codex `model/list` observations do not provide QuotaPilot's relative
power/cost/latency heuristics or a verified effort ordering. Those discovered
models remain preserved but are not automatically routable until an external
capability/fallback definition layer supplies explicit normalized metadata.
This is a deliberate safe limitation, not a reason to infer tiers from model
IDs.
