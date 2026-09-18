# QuotaPilot Phase 6 — Controlled Execution & Agent Integration Contract

Status: Implemented normative contract (2026-09-18)
Phase: 6
Depends on:

- Phase 2 — Provider boundary
- Phase 3 / 3.1 — Persistence boundary
- Phase 4 / 4.1 — Budget Engine
- Phase 5 — Quota-aware Routing Engine
- Phase 5.5 — Capability Metadata & Routing Calibration

Phase 6 introduces controlled execution of routing recommendations.

---

## 1. Purpose

Phase 6 turns QuotaPilot from a recommendation engine into a controlled execution layer.

The system already produces:

```text
TaskProfile
+
BudgetReport
+
Enriched CapabilitySet
+
RoutingPolicy
↓
RoutingRecommendation
```

Phase 6 adds:

```text
RoutingRecommendation
↓
Execution Plan
↓
Policy / Approval Gate
↓
Controlled Agent Invocation
↓
Execution Result
↓
Optional Escalation Recommendation
```

Phase 6 MUST preserve human control.

The system must never silently execute an expensive or destructive action merely because a routing recommendation exists.

---

## 2. Primary goals

Phase 6 MUST support:

- execution planning from `RoutingRecommendation`,
- dry-run mode,
- explicit execution policy,
- controlled model/effort invocation,
- safe subprocess boundaries,
- bounded retries,
- bounded escalation,
- quota re-check before execution,
- execution result capture,
- structured failure classification,
- explainable escalation decisions,
- user-visible execution summaries,
- auditability without collecting unnecessary private data.

Phase 6 SHOULD support:

- Codex CLI integration,
- future Claude Code integration,
- execution adapters,
- optional manual confirmation policies,
- non-interactive policy mode for explicitly allowed tasks.

Phase 6 MUST NOT implement:

- unbounded autonomous loops,
- hidden background agents,
- silent cross-provider fallback,
- automatic profile mutation,
- remote telemetry by default,
- arbitrary shell execution from provider output,
- unrestricted recursive self-delegation.

---

## 3. Core principle

A recommendation is not permission to execute.

The system must preserve a strict boundary:

```text
RoutingRecommendation
!=
ExecutionAuthorization
```

Execution requires both:

```text
valid recommendation
+
execution policy allows action
```

and, where configured:

```text
explicit human approval
```

---

## 4. Canonical execution flow

```text
Task Input
   ↓
TaskProfile
   ↓
BudgetReport
   ↓
Enriched CapabilitySet
   ↓
RoutingRecommendation
   ↓
ExecutionPlanner
   ↓
ExecutionPlan
   ↓
Quota Re-check
   ↓
ExecutionPolicy Gate
   ↓
Executor Adapter
   ↓
ExecutionResult
   ↓
EscalationEvaluator
   ↓
Optional Next ExecutionPlan
```

The routing engine remains advisory and provider-independent.

The execution layer consumes routing output.

---

## 5. Architecture boundaries

Suggested new package:

```text
src/quotapilot/execution/
```

Possible structure:

```text
execution/
├── __init__.py
├── models.py
├── planner.py
├── policy.py
├── executor.py
├── escalation.py
├── errors.py
└── adapters/
    ├── __init__.py
    └── codex_cli.py
```

The exact split is implementation-defined.

Provider-specific invocation logic belongs under adapters.

The core execution package MUST NOT contain hardcoded Codex/Claude logic outside adapters.

---

## 6. Separation of concerns

### Routing Engine

Responsible for:

- recommended model,
- recommended effort,
- escalation path,
- explanation.

### Execution Planner

Responsible for converting recommendation into an executable plan.

### Execution Policy

Responsible for deciding whether execution is:

- allowed,
- requires approval,
- denied.

### Execution Adapter

Responsible for invoking a specific external tool.

### Escalation Evaluator

Responsible for deciding whether another recommended step may be attempted.

Do not merge all responsibilities into one class.

---

## 7. ExecutionPlan

Introduce a provider-neutral execution plan.

Conceptual model:

```python
class ExecutionPlan(BaseModel):
    execution_id: str

    provider: str
    model_id: str
    effort: str | None

    task_payload: str | None

    source_recommendation_id: str | None

    attempt_number: int
    max_attempts: int

    requires_confirmation: bool
    dry_run: bool

    quota_snapshot_captured_at: datetime | None
    budget_pressure: float | None

    metadata: dict[str, Any] = {}
```

The actual schema may differ.

Requirements:

- deterministic construction,
- explicit attempt number,
- explicit dry-run,
- explicit approval requirement,
- no hidden escalation state.

---

## 8. ExecutionResult

Introduce a structured result.

Conceptually:

```python
class ExecutionResult(BaseModel):
    execution_id: str
    started_at: datetime
    finished_at: datetime

    model_id: str
    effort: str | None

    status: ExecutionStatus

    exit_code: int | None
    stdout_summary: str | None
    stderr_summary: str | None

    failure_class: FailureClass | None

    escalation_recommended: bool
    next_step: RoutingStep | None

    metadata: dict[str, Any] = {}
```

Avoid automatically storing full raw stdout/stderr unless explicitly necessary.

---

## 9. ExecutionStatus

Suggested enum:

```text
planned
dry_run
awaiting_approval
running
succeeded
failed
cancelled
denied
quota_changed
```

Exact names may vary.

The state machine must be deterministic and testable.

---

## 10. Dry-run mode

Dry-run is mandatory.

Example:

```bash
quotapilot execute "Fix typo in README" --dry-run
```

Dry-run should show:

- selected model,
- effort,
- current quota pressure,
- planned command/adapter,
- approval requirement,
- escalation limit,
- what would be executed.

Dry-run MUST NOT invoke the external agent.

---

## 11. Approval policy

Execution policy should support at least:

```text
always_confirm
confirm_on_escalation
auto_for_low_risk
never_execute
```

The exact policy names are implementation-defined.

Default behavior SHOULD be conservative.

Recommended initial default:

```text
always_confirm
```

for real execution.

Non-interactive auto-execution should require explicit policy configuration.

---

## 12. Approval boundary

Human approval should apply to the plan as shown.

If any material field changes after approval, the plan must be reconsidered.

Material fields include:

- model,
- effort,
- provider,
- task payload,
- escalation step,
- quota pressure crossing policy threshold.

Do not reuse approval for a materially different plan.

---

## 13. Quota re-check

Before actual execution, QuotaPilot must re-evaluate current quota state.

Reason:

```text
recommendation time
!=
execution time
```

The system should detect if:

- snapshot is stale,
- quota pressure materially increased,
- binding pool changed,
- previously allowed recommendation is no longer allowed.

If material quota state changed:

```text
status = quota_changed
```

and execution should be re-planned or require renewed approval.

---

## 14. Snapshot freshness

Execution must not rely on arbitrarily stale budget state.

Introduce an execution freshness threshold.

If the latest snapshot exceeds the threshold:

- refresh through the existing provider/service path when explicitly allowed,
- otherwise stop and request refresh.

The pure execution planner must not itself call provider RPC.

Refresh orchestration belongs in service/composition code.

---

## 15. Controlled escalation

Escalation must be bounded.

The existing Phase 5 recommendation may contain:

```text
escalation_path
```

Phase 6 may execute at most the configured number of steps.

Recommended initial constraints:

```text
max_attempts = 2 or 3
```

No unbounded retry loop.

No recursive self-escalation beyond the recommendation path.

---

## 16. Escalation conditions

Escalation should occur only on structured failure signals.

Examples:

```text
explicit execution failure
validation failure
non-zero exit
known retryable agent failure
```

Do not escalate merely because output "looks weak" without an explicit evaluator.

Content-quality judgment using another LLM is out of scope for initial Phase 6.

---

## 17. No hidden self-critique loop

Do not implement:

```text
agent runs
→ agent judges itself
→ agent escalates itself
→ repeat forever
```

Initial escalation must remain bounded and rule-based.

Future evaluator agents require a separate contract.

---

## 18. Failure taxonomy

Introduce structured failure classes.

Suggested categories:

```text
transport
authentication
quota
timeout
agent_error
validation
execution_environment
user_cancelled
unknown
```

This taxonomy should help determine whether escalation is appropriate.

Example:

```text
authentication failure
```

should not trigger stronger-model escalation.

---

## 19. Retry vs escalation

Retry and escalation are distinct.

### Retry

Same model/effort, usually for transient execution failure.

### Escalation

Different model and/or effort.

The execution layer must keep them separate.

Do not consume escalation steps for a simple transient transport retry unless policy explicitly says so.

---

## 20. Retry limits

Retries must be bounded.

Recommended:

```text
max_same_step_retries = 1
```

for initial implementation.

Retryable errors must be explicitly classified.

Do not retry:

- authentication errors,
- invalid configuration,
- denied execution,
- malformed plan.

---

## 21. Provider adapters

Execution adapters should implement a provider-neutral protocol.

Conceptually:

```python
class ExecutionAdapter(Protocol):
    async def execute(
        self,
        plan: ExecutionPlan,
    ) -> ExecutionResult:
        ...
```

Initial adapter:

```text
Codex CLI
```

Future adapter:

```text
Claude Code
```

The core planner/policy layer should not depend on Codex-specific subprocess details.

---

## 22. Codex CLI adapter

The initial Codex adapter must determine the currently supported invocation syntax from the installed CLI.

Do not assume stale CLI flags.

Before implementation, verify:

- model selection flag,
- effort/reasoning flag,
- non-interactive invocation mode,
- working-directory handling,
- input/task passing,
- exit semantics.

Document verified behavior.

---

## 23. No browser automation

Phase 6 must not execute ChatGPT through browser automation.

Use supported local/CLI interfaces only.

Do not scrape web sessions or browser cookies.

---

## 24. Task payload handling

Task text may contain private code/project information.

Default behavior:

- keep task payload in memory,
- pass only to selected executor,
- do not persist automatically.

If execution audit persistence is added, raw task text should be excluded by default.

Use:

```text
task_hash
task_class
profile dimensions
```

for audit where possible.

---

## 25. Execution audit

A lightweight local audit MAY be implemented.

Recommended persisted fields:

```text
execution_id
timestamp
provider
model
effort
attempt number
status
failure class
quota pressure
task hash
```

Avoid storing:

- raw prompt,
- source code,
- full stdout,
- full stderr,
- credentials.

Audit storage must remain local by default.

---

## 26. Task hash

If task correlation is useful, use a one-way digest.

Example:

```text
SHA-256(task text)
```

This is not secret encryption.

It is only a stable local correlation identifier.

Do not claim reversibility protection against low-entropy task strings.

---

## 27. Working directory safety

Execution plan must specify working directory explicitly.

Do not inherit an arbitrary unexpected directory silently.

For repository tasks:

```text
cwd = current repository root
```

should be explicit.

Adapters must not traverse into unrelated directories unless explicitly requested.

---

## 28. Shell safety

Avoid constructing shell command strings where structured subprocess arguments are possible.

Prefer:

```python
asyncio.create_subprocess_exec(...)
```

over:

```python
create_subprocess_shell(...)
```

Do not interpolate untrusted task text into shell syntax.

Task payload should be passed through supported stdin/argument mechanisms safely.

---

## 29. Environment safety

Execution adapters should use a controlled inherited environment.

Do not print environment variables.

Do not persist:

- API keys,
- SSH keys,
- tokens,
- cookies.

Sensitive environment values must not appear in logs.

---

## 30. Timeout

Every real external execution must have a configurable timeout.

Timeout must produce a structured failure.

Example:

```text
failure_class = timeout
```

Timeout should not automatically escalate unless policy allows it.

---

## 31. Cancellation

Support user cancellation where practical.

Cancellation should:

- terminate the child process safely,
- reap subprocesses,
- return `cancelled`,
- not trigger escalation.

---

## 32. Subprocess cleanup

Adapters must safely handle:

- process exit,
- stdout/stderr drain,
- timeout,
- cancellation,
- broken pipes,
- partial output.

No zombie child processes.

No reader task leaks.

---

## 33. Output capture

Output capture should be bounded.

Do not buffer unlimited stdout/stderr.

Recommended:

```text
bounded tail
```

or size limit.

The full external-agent transcript need not be persisted.

CLI may stream output while retaining only bounded summary metadata.

---

## 34. Secret redaction

Before any execution log/audit persistence:

- redact known credential-like values,
- avoid storing raw environment,
- avoid serializing full provider state.

Reuse existing redaction logic where appropriate rather than creating conflicting rules.

---

## 35. ExecutionPolicy

Introduce a strict policy model.

Conceptually:

```python
class ExecutionPolicy(BaseModel):
    mode: ExecutionMode
    max_attempts: int
    max_same_step_retries: int
    timeout_seconds: int
    require_fresh_budget: bool
    max_budget_age_seconds: int
    allow_escalation: bool
```

Use strict validation and `extra="forbid"`.

---

## 36. Risk-aware execution gate

The execution gate MAY consider task risk.

Examples:

- low-risk mechanical task,
- high-risk repository-wide change,
- security-sensitive task.

However, Phase 6 should rely on existing `TaskProfile` dimensions rather than brittle keyword detection.

Potential policy:

```text
high failure_cost
→ confirmation required
```

even if normal policy allows low-risk automatic execution.

---

## 37. Dry-run CLI

Suggested command:

```bash
quotapilot execute "Fix typo in README" --dry-run
```

Output should include:

```text
Recommended model
Effort
Quota pressure
Task risk
Execution adapter
Working directory
Approval requirement
Max attempts
Escalation path
```

No execution occurs.

---

## 38. Real execution CLI

Possible command:

```bash
quotapilot execute "Fix typo in README"
```

Default should require confirmation unless explicitly configured otherwise.

A non-interactive flag may exist only with explicit execution policy.

Example:

```bash
quotapilot execute "..." --yes
```

must still obey policy gates.

`--yes` is not permission to bypass hard safety/policy constraints.

---

## 39. JSON execution plan

Support:

```bash
quotapilot execute "..." --dry-run --json
```

The JSON should serialize a safe execution plan.

It must not expose:

- credentials,
- raw provider metadata,
- private environment values.

---

## 40. Plan identity

Every plan should have a unique execution ID.

Random UUID is acceptable for orchestration identity.

Unlike routing core, execution identity need not be deterministic.

The plan contents themselves should remain inspectable and stable.

---

## 41. Recommendation binding

ExecutionPlan should record which recommendation it came from.

If routing recommendation changes before execution, the plan should be invalidated or rebuilt.

Do not execute a stale plan against a materially changed recommendation.

---

## 42. Capability re-validation

Immediately before execution, verify:

- model still exists,
- model is selectable,
- effort is still supported,
- profile is not newly stale/invalid.

If not:

```text
deny/replan
```

Do not blindly execute a model removed from current capabilities.

---

## 43. Quota gate

Execution policy should reject or require reapproval when current budget pressure violates configured limits.

Example configurable rule:

```text
CRITICAL pressure
+
low-risk task
→ deny expensive escalation
```

But capability floor from Phase 5 still applies.

Do not replace routing policy with execution policy.

---

## 44. Cost-aware escalation

Escalation should re-check quota before each stronger step.

The quota situation may have changed after an attempt.

Never assume the entire original escalation path remains affordable.

---

## 45. Result validation

Initial Phase 6 should use structural execution success signals only.

Examples:

- exit status,
- executor-reported completion,
- optional configured test command.

Do not automatically ask another LLM to judge semantic quality in initial Phase 6.

---

## 46. Optional verification command

ExecutionPolicy MAY support a safe explicit verification command defined by the user/project.

Examples:

```text
pytest
ruff check
```

This must be explicitly configured.

Do not derive arbitrary shell commands from agent output.

Verification commands themselves should use structured subprocess arguments where possible.

---

## 47. Verification outcome

If an explicit verification command fails:

```text
failure_class = validation
```

Escalation MAY be recommended if policy allows.

The verification failure details should be bounded and sanitized.

---

## 48. No arbitrary tool execution from model output

The external agent may produce text suggesting commands.

QuotaPilot MUST NOT parse arbitrary model prose and automatically execute those commands.

Only the configured execution adapter itself may operate according to its supported interface.

Future autonomous tool execution requires a separate security contract.

---

## 49. Execution service

Suggested service:

```text
src/quotapilot/services/execution.py
```

Responsibilities:

```text
route task
↓
refresh/retrieve budget
↓
build plan
↓
policy gate
↓
invoke adapter
↓
process result
↓
optional bounded escalation
```

Keep CLI thin.

---

## 50. Execution planner purity

Where practical, planning should be pure:

```text
RoutingRecommendation
+
ExecutionPolicy
+
TaskProfile
+
current BudgetReport
↓
ExecutionPlan
```

Subprocess execution belongs only to adapters/services.

---

## 51. No hidden persistence

Execution should not automatically store raw task/output content.

If audit persistence exists, only store explicitly allowed metadata.

This must be documented.

---

## 52. Test matrix — planning

Test:

- dry-run,
- approval required,
- approval not required by explicit low-risk policy,
- stale budget,
- quota changed,
- model removed,
- unsupported effort,
- disabled escalation,
- max attempts.

---

## 53. Test matrix — execution adapter

Using fake executors, test:

- successful execution,
- non-zero exit,
- timeout,
- cancellation,
- malformed adapter response,
- broken pipe,
- stdout limit,
- stderr limit,
- cleanup.

Normal tests must not invoke real Codex.

---

## 54. Test matrix — policy

Test:

- `never_execute`,
- `always_confirm`,
- low-risk auto policy,
- high failure-cost override,
- CRITICAL quota behavior,
- stale profile behavior,
- stale budget behavior.

---

## 55. Test matrix — escalation

Test:

- initial success → no escalation,
- retryable transport failure → bounded retry,
- validation failure → escalation if configured,
- auth failure → no escalation,
- timeout → policy-dependent,
- escalation path exhausted,
- max attempts reached,
- quota changed before escalation.

---

## 56. Test matrix — privacy

Test that audit/output does not include:

- raw account ID,
- token,
- environment secret,
- raw provider metadata,
- full task text when persistence is enabled by default.

---

## 57. Integration tests

Opt-in real integration may test:

```text
task
↓
route
↓
dry-run plan
```

without executing external agent.

A separate explicit environment variable should gate real execution tests.

Recommended:

```text
QUOTAPILOT_EXECUTION_INTEGRATION=1
```

Do not use the normal integration flag alone to trigger real model execution.

---

## 58. Real execution integration safety

Real execution tests must:

- use a harmless temporary repository,
- use a trivial task,
- avoid destructive operations,
- have timeout,
- have bounded output,
- never run in the QuotaPilot repo itself unless explicitly intended.

Example safe task:

```text
Create or edit a temporary text file in a temp repo.
```

No network-sensitive or destructive task.

---

## 59. CLI observability

The CLI should clearly show:

```text
planned
awaiting approval
executing
succeeded
failed
retrying
escalating
cancelled
```

Avoid vague silent state changes.

---

## 60. Auditability

Users should be able to answer:

```text
Why was this model executed?
Why this effort?
What quota state was used?
Was the user asked for approval?
Why did escalation occur?
```

The execution record should preserve enough metadata to explain this without preserving unnecessary private content.

---

## 61. Phase 6 non-goals

Phase 6 does NOT include:

- general autonomous coding agent framework,
- multi-agent debate,
- automatic semantic evaluator,
- task decomposition,
- web/cloud orchestration,
- distributed execution,
- remote queueing,
- team collaboration,
- autonomous policy learning.

These require separate later phases.

---

## 62. Acceptance criteria

Phase 6 is complete when:

1. Controlled execution package exists.
2. ExecutionPlan exists.
3. ExecutionResult exists.
4. Strict ExecutionPolicy exists.
5. Dry-run works.
6. Approval gate works.
7. Quota re-check works.
8. Capability re-validation works.
9. Codex CLI adapter exists.
10. Provider-specific logic remains inside adapters.
11. Safe subprocess execution is used.
12. Timeout/cancellation work.
13. Retry is bounded.
14. Escalation is bounded.
15. Auth/config failures do not escalate.
16. Quota is re-checked before escalation.
17. Raw task text is not automatically persisted.
18. Output capture is bounded.
19. CLI execution command exists.
20. JSON dry-run exists.
21. Offline tests do not invoke real agents.
22. Optional real-execution integration is separately gated.
23. Ruff passes.
24. Pyright passes.
25. Privacy/security review passes.
26. Git working tree is clean after commit/push.

---

## 63. Completion boundary

At the end of Phase 6:

```text
Task
↓
Budget + Capabilities
↓
RoutingRecommendation
↓
Controlled ExecutionPlan
↓
Policy / Approval
↓
External Agent Adapter
↓
ExecutionResult
↓
Optional bounded escalation
```

QuotaPilot may then operate as a controlled quota-aware agent orchestration layer.

It must still preserve explicit user policy and bounded execution.

---

## 64. Phase 7 preview

A later phase may add:

- Waybar integration,
- richer TUI,
- notifications,
- long-term calibration feedback,
- provider plugins,
- safer automatic low-risk execution presets.

These are not part of Phase 6.

---

## 65. Implemented Phase 6 behavior

The implementation follows this contract with the following concrete v0.1
choices:

- `ExecutionPolicy.mode` defaults to `always_confirm`; `never_execute`,
  `confirm_on_escalation`, and `auto_for_low_risk` are explicit alternatives.
  Task risk is evaluated from `TaskProfile` dimensions, never task keywords.
- A dry-run consumes only the latest persisted snapshot. It never starts the
  provider or execution adapter. A real plan may capture when persisted data
  is absent/stale, but every actual attempt performs a new coherent provider
  capture after any required approval.
- Material pressure change means a pressure delta greater than the configured
  threshold, a known/unknown pressure transition, or a changed binding pool.
  Such change stops with `quota_changed`; it is never accepted silently.
- Current exact capabilities are re-enriched and re-routed before every
  attempt. Removed/non-selectable models, unsupported efforts, newly stale
  profiles, or a changed recommendation stop with `capability_changed`.
- Same-step retries default to one and only `transport` is retryable by
  default. `agent_error` and explicit `validation` failure may consume the
  existing Phase 5 escalation path. Authentication, quota, execution-
  environment, cancellation, and (by default) timeout failures do not retry
  or escalate. Maximum attempts default to three.
- No execution audit is persisted in v0.1. Raw tasks and complete agent output
  remain in memory. Safe JSON contains a SHA-256 task correlation digest and
  task class, while stdout/stderr metadata retains only separately bounded,
  credential-redacted tails.

### Verified Codex CLI adapter (Codex CLI 0.155.0)

The installed CLI was inspected on 2026-09-18. Non-interactive execution uses
`codex exec`; the global approval option must precede that subcommand. QuotaPilot
uses structured arguments equivalent to:

```text
codex --ask-for-approval never exec --ephemeral \
  --model MODEL \
  --config model_reasoning_effort="EFFORT" \
  --sandbox workspace-write \
  --cd WORKING_DIRECTORY \
  --color never \
  -
```

The task is written to stdin and never interpolated into shell syntax. The
outer QuotaPilot approval gate is the execution authorization; the inner
non-interactive Codex process cannot open an unobserved approval prompt.
`create_subprocess_exec` is used with an explicit working directory, timeout,
process reaping, and concurrent bounded stdout/stderr drains.

Normal integration remains gated by `QUOTAPILOT_INTEGRATION=1` and cannot
execute an agent. Any future paid/real execution test must additionally use
`QUOTAPILOT_EXECUTION_INTEGRATION=1`; no such test is enabled in Phase 6.
