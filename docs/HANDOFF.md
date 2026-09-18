# QuotaPilot Development Handoff

> Shared current-state window for Claude Code and Codex. Read the technical
> design, phase contracts, and decision log before continuing.

## Current state

- Date: 2026-09-18
- Last agent: Codex
- Current phase: **Phase 6 controlled execution complete**
- Phase 2 provider boundary: **COMPLETE**
- Phase 3/3.1 persistence boundary: **COMPLETE**
- Phase 4/4.1 budget boundary: **COMPLETE**
- Phase 5 routing boundary: **COMPLETE**
- Phase 5.5 enrichment/calibration boundary: **COMPLETE**
- Phase 6 controlled execution boundary: **COMPLETE**
- Phase 7 implementation: **NOT STARTED**
- Phase 7 readiness: **READY**, subject to the limitations below

The normative and implemented Phase 6 contract is
`docs/PHASE6_EXECUTION_CONTRACT.md`.

## Phase 6 implementation

### Execution boundary

- `src/quotapilot/execution/` contains strict `ExecutionPlan`,
  `ExecutionResult`, `ExecutionPolicy`, status/failure enums, pure planning and
  risk-based authorization, bounded retry/escalation, output redaction, and a
  provider-neutral adapter protocol.
- A `RoutingRecommendation` remains advisory. The default real-execution mode
  is `always_confirm`; dry-run never requires approval and never invokes the
  provider or external agent. `never_execute`, `confirm_on_escalation`, and
  `auto_for_low_risk` are explicit strict-policy alternatives.
- Plans contain a random execution ID, provider/model/effort, attempt bounds,
  explicit working directory, timeout, quota context, recommendation digest,
  task class/hash, and the advisory escalation path. Raw task/profile summary
  remain in memory and are excluded from serialized plan JSON.
- No execution audit storage was introduced. Raw tasks, transcripts,
  environment variables, provider responses, and account identity are not
  persisted by Phase 6.

### Revalidation and state machine

- `ExecutionService` uses the existing route stack. Every real attempt occurs
  only after approval (when required), then a fresh coherent
  `provider.capture_usage()`, budget recomputation, exact capability
  enrichment, and route re-evaluation with the original audited task profile.
- Known/unknown pressure transitions, pressure change greater than the policy
  threshold, or changed binding pool stop as `quota_changed`. Removed or
  non-selectable models, unsupported efforts, newly stale/unroutable profile
  data, changed escalation steps, or changed initial recommendation stop as
  `capability_changed`; no silent substitution occurs.
- Retry preserves model/effort and defaults to one transport retry. Escalation
  consumes only the Phase 5 escalation path, requires renewed approval for the
  changed plan, and rechecks quota/capability first. Maximum attempts default
  to three. Authentication, quota, environment, cancellation, and timeout do
  not retry/escalate by default; cancellation never escalates.

### Codex CLI adapter

- Installed `codex-cli 0.155.0` was inspected directly. The adapter uses
  `codex --ask-for-approval never exec --ephemeral --model … --config
  model_reasoning_effort=… --sandbox workspace-write --cd … --color never -`.
- `--ask-for-approval` is a global option and must precede `exec`; task text is
  sent through stdin. `asyncio.create_subprocess_exec` is used—there is no
  shell string, `shell=True`, or task interpolation.
- The process has an explicit cwd and timeout. stdout/stderr are drained
  concurrently into separately bounded tails, then credential patterns are
  redacted. Timeout, cancellation, and broken pipes terminate/reap the child.

### CLI

- `quotapilot execute TASK --dry-run` renders classification, model/effort,
  quota/binding context, adapter, cwd, approval, timeout, attempt bound, and
  escalation path without live capture or execution.
- `quotapilot execute TASK --dry-run --json` emits a safe `ExecutionPlan`
  projection without raw task/account/provider metadata.
- `quotapilot execute TASK` defaults to an interactive confirmation. A changed
  escalation plan is displayed and confirmed separately. No `--yes` bypass
  was introduced.

## Verification

Commands run from the repository root:

```bash
uv run pytest
uv run ruff check .
uv run pyright
uv run quotapilot --help
uv run quotapilot execute --help
QUOTAPILOT_INTEGRATION=1 uv run pytest tests/integration/
```

Results:

- Offline/default pytest: **392 passed, 5 skipped**. The five skips are the
  explicitly gated authenticated live tests.
- Phase 6-focused tests: **45 passed**. They cover strict planning/policy,
  dry-run privacy, confirmation, live revalidation, stale profiles, material
  quota change, bounded retry/escalation, max attempts, removed models,
  unsupported efforts, auth/quota/timeout/cancel behavior, structured
  subprocess invocation, bounded/redacted output, timeout, cancellation,
  broken pipes, and process cleanup.
- Normal authenticated integration: **5 passed**. It remains capture/profile/
  budget/route-only and does not import or invoke the execution adapter.
- Real execution integration: **NOT RUN**. No paid/real execution test is
  enabled; any future one must require `QUOTAPILOT_EXECUTION_INTEGRATION=1` in
  addition to its own safe temporary-repository fixture.
- Ruff: **All checks passed**.
- Pyright: **0 errors, 0 warnings, 0 informations**.
- Root and execute CLI help: **PASS**.

Normal CI remains offline, credential-free, and incapable of real model use.

## Security/privacy review

- No `create_subprocess_shell`, `shell=True`, arbitrary command extraction,
  unbounded output buffering, unbounded retry, or recursive delegation exists.
- Output retention is bounded before decoding/redaction. Plans/results never
  serialize the inherited environment or raw provider response.
- No credential, token, cookie, raw account ID, live telemetry, private task,
  full transcript, cache, or generated artifact was added.
- Existing snapshot pseudonymization and profile safe-YAML boundaries remain
  unchanged.

## Remaining risks / deferred decisions

- Current Codex CLI syntax was verified for 0.155.0 and must be revalidated
  when the installed CLI changes; there is not yet a machine-readable CLI
  compatibility negotiation layer.
- Non-zero Codex failures use conservative stable marker classification for
  authentication/quota; other non-zero exits are `agent_error`. Richer
  machine-readable CLI failure envelopes are not currently available.
- Phase 6 does not run a post-execution semantic evaluator or project test
  command. Explicit verification commands remain optional future work under a
  separate command-security design.
- Capability scores and routing calibration remain provisional Phase 5.5
  policy. Execution does not alter or auto-calibrate them.
- No execution audit is persisted; only the in-memory result explains a run.
- Long-lived versus ephemeral Codex app-server capture remains deferred.

## Next task

Phase 7 may add the separately contracted observability/user-integration work.
It must preserve the recommendation/authorization split, the independent real
execution integration gate, bounded subprocess behavior, and no raw task or
transcript persistence by default.
