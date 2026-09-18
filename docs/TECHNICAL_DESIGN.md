# QuotaPilot v0.1 Technical Design

- Version: 0.1
- Status: Implementation-ready draft
- Primary target: OpenAI Codex CLI
- Future targets: Claude Code and other quota-based AI coding tools
- Last design update: 2026-09-18

## 1. Purpose

QuotaPilot is a local usage-management and model-routing assistant for subscription-based AI coding tools.

Its goals are to:

1. Observe current quota / rate-limit state.
2. Normalize provider-specific usage into a provider-independent representation.
3. Calculate whether the user is underusing or overusing available quota.
4. Estimate how much quota may reasonably be used today.
5. Recommend an appropriate model and reasoning/effort level for a task.
6. Prefer lighter models when they are sufficient.
7. Escalate to stronger models when required.
8. Adapt to subscription-plan and quota-policy changes.
9. Avoid hardcoding plan behavior wherever live capabilities can be discovered.
10. Eventually integrate directly into Codex and Claude Code workflows.

QuotaPilot is not merely a usage dashboard.

Core abstraction:

```text
Recommendation = f(task, quota_state, user_policy)
```

The user always retains the final decision.

---

## 2. Core design principles

### 2.1 Quota-pool-first, not plan-name-first

Do not make plan names the primary source of truth.

Avoid:

```python
if plan == "pro":
    ...
elif plan == "plus":
    ...
```

Prefer:

```text
Account
├── capabilities
├── available models
├── quota pools
├── quota bindings
└── credits / fallback mechanisms
```

Plan names such as Go / Plus / Pro are metadata and may be used for fallback definitions only.

Priority order for truth:

1. Live provider/account data
2. Provider model catalog
3. Provider rate-limit information
4. Remotely maintained definitions
5. Bundled fallback definitions

### 2.2 Provider-independent core

The budget engine and routing engine must not know about OpenAI-specific RPC structures.

### 2.3 Recommendation before automation

v0.1 recommends models but does not automatically switch models, spend credits, or launch delegated agents.

### 2.4 Preserve unknown data

Unknown models, quota types, and provider fields must not crash the program. Preserve raw information in metadata and expose uncertainty explicitly.

### 2.5 Explainable decisions

Every routing recommendation must explain:

- why this model,
- why not a weaker model,
- why not a stronger model,
- what would trigger escalation.

---

## 3. v0.1 scope

### MUST implement

- OpenAI Codex provider
- account information retrieval
- quota/rate-limit retrieval
- quota normalization
- local snapshot persistence
- weekly pacing
- daily budget
- reserve quota
- underuse detection
- overuse detection
- CLI dashboard
- model recommendation
- effort/reasoning recommendation
- escalation recommendation
- configurable routing policies
- JSON output
- Waybar-compatible output
- unit tests
- fixture-based provider parser tests

### SHOULD implement

- local Codex usage-history parsing
- plan/capability fallback definitions
- unknown-model handling
- configurable weekday weights

### MUST NOT implement in v0.1

- automatic model switching
- automatic subagent delegation
- automatic credit spending
- account-setting modifications
- browser UI scraping
- browser cookie/session extraction
- credit purchasing
- assumptions that quota percentages directly equal token percentages

---

## 4. Technology stack

- Python >= 3.12
- Pydantic v2
- Typer
- Rich
- aiosqlite
- platformdirs
- PyYAML
- pytest
- pytest-asyncio

Recommended development tooling:

- uv
- ruff
- pyright or mypy
- GitHub Actions

Optional later:

- Textual for a TUI

CLI executable:

```text
quotapilot
```

---

## 5. Repository layout

```text
QuotaPilot/
├── README.md
├── CLAUDE.md
├── AGENTS.md
├── pyproject.toml
├── .gitignore
├── .python-version
├── docs/
│   ├── TECHNICAL_DESIGN.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── DECISIONS.md
│   ├── HANDOFF.md
│   ├── AGENT_MODEL_POLICY.md
│   ├── architecture.md
│   ├── provider-contract.md
│   ├── quota-model.md
│   └── routing.md
├── prompts/
│   └── CLAUDE_CODE_BOOTSTRAP.md
├── src/
│   └── quotapilot/
│       ├── __init__.py
│       ├── domain/
│       │   ├── account.py
│       │   ├── capability.py
│       │   ├── model.py
│       │   ├── quota.py
│       │   ├── usage.py
│       │   ├── task.py
│       │   └── recommendation.py
│       ├── providers/
│       │   ├── base.py
│       │   └── openai_codex/
│       │       ├── provider.py
│       │       ├── app_server.py
│       │       ├── rpc.py
│       │       ├── parser.py
│       │       ├── models.py
│       │       └── fallback.yaml
│       ├── budget/
│       │   ├── engine.py
│       │   ├── pace.py
│       │   ├── allocation.py
│       │   └── reserve.py
│       ├── routing/
│       │   ├── engine.py
│       │   ├── complexity.py
│       │   ├── policy.py
│       │   ├── scoring.py
│       │   └── escalation.py
│       ├── capabilities/
│       │   ├── models.py
│       │   ├── loader.py
│       │   ├── registry.py
│       │   └── enrichment.py
│       ├── calibration/
│       │   ├── models.py
│       │   ├── loader.py
│       │   └── evaluator.py
│       ├── history/
│       │   ├── repository.py
│       │   ├── codex_logs.py
│       │   └── sqlite.py
│       ├── config/
│       │   ├── loader.py
│       │   ├── schema.py
│       │   └── defaults.yaml
│       ├── services/
│       │   ├── snapshot.py
│       │   ├── status.py
│       │   └── advisor.py
│       └── cli/
│           ├── app.py
│           ├── status.py
│           ├── route.py
│           ├── history.py
│           ├── doctor.py
│           └── waybar.py
└── tests/
    ├── unit/
    ├── integration/
    ├── fixtures/
    └── golden/
```

Do not create all implementation files in one commit merely to match this tree. Create directories/files as phases need them.

---

## 6. Domain model

### 6.1 AccountInfo

```python
class AccountInfo(BaseModel):
    provider: str
    account_id: str | None
    plan_name: str | None
    capabilities: "CapabilitySet"
    observed_at: datetime
```

`plan_name` is informational. Business logic must not depend solely on it.

### 6.2 AIModel

```python
class AIModel(BaseModel):
    id: str
    provider: str
    family: str | None = None

    selectable: bool = True
    supported_efforts: tuple[str, ...] = ()
    effort_order: tuple[str, ...] | None = None

    relative_power: float | None = None
    relative_cost: float | None = None
    relative_latency: float | None = None

    metadata: dict[str, Any] = {}
```

`relative_*` fields are QuotaPilot routing heuristics, not official provider specifications.
`effort_order`, when present, is the normalized least-to-greatest order and
must contain every supported effort exactly once. An unordered catalog is
preserved but cannot drive an effort recommendation.

### 6.3 CapabilitySet

```python
class CapabilitySet(BaseModel):
    models: list[AIModel]
    supports_reasoning_effort: bool = False
    supports_credits: bool = False
    supports_model_selection: bool = False
    metadata: dict[str, Any] = {}
```

Unknown models should still be surfaced with `routing_status = unknown` or equivalent metadata.

---

## 7. Quota model

### 7.1 QuotaPool

```python
class QuotaPool(BaseModel):
    id: str
    provider: str

    kind: Literal[
        "rolling",
        "fixed",
        "credit",
        "unknown",
    ]

    scope: Literal[
        "account",
        "product",
        "model",
        "model_group",
        "unknown",
    ]

    used_fraction: float | None
    remaining_fraction: float | None

    starts_at: datetime | None
    resets_at: datetime | None
    window_seconds: int | None

    applies_to_models: list[str] = []

    raw_name: str | None = None
    metadata: dict[str, Any] = {}
```

All fractions are normalized to 0.0–1.0 when the provider exposes enough information.

### 7.2 QuotaBinding

```python
class QuotaBinding(BaseModel):
    model_id: str
    reasoning_effort: str | None = None
    quota_pool_ids: list[str]

    confidence: Literal[
        "provider",
        "observed",
        "fallback",
        "unknown",
    ]
```

Bindings are many-to-many. Never assume one model equals one quota.

### 7.3 UsageSnapshot

```python
class UsageSnapshot(BaseModel):
    account: AccountInfo
    quota_pools: list[QuotaPool]
    quota_bindings: list[QuotaBinding]
    captured_at: datetime
```

Snapshots are persisted locally to enable historical analysis.

---

## 8. Provider interface

```python
class UsageProvider(Protocol):
    async def capture_usage(self) -> UsageSnapshot: ...
    async def get_account(self) -> AccountInfo: ...
    async def get_models(self) -> list[AIModel]: ...
    async def get_quota_pools(self) -> list[QuotaPool]: ...
    async def get_quota_bindings(self) -> list[QuotaBinding]: ...
    async def healthcheck(self) -> ProviderHealth: ...
```

Provider-specific response structures must not leak into budget/routing layers.

`capture_usage()` is the only coherent-observation API. It returns account,
quota pools, and bindings from one provider capture with one `captured_at`.
Persistence and any consumer that needs a mutually consistent observation
must use it. The individual getters are independent point reads; results from
sequential getter calls must not be combined and described as atomic.

---

## 9. OpenAI Codex provider

Preferred integration path:

```text
Codex CLI
   ↓
app-server
   ↓
account / rate-limit RPC
   ↓
OpenAI Codex provider adapter
   ↓
QuotaPilot normalized domain
```

At implementation time, verify the exact current RPC method names and payloads against the installed Codex CLI instead of blindly assuming this document is current.

Expected current candidates include account and rate-limit read operations such as:

```text
account/read
account/rateLimits/read
```

The adapter is responsible for:

1. launching or connecting to `codex app-server`,
2. handling JSON-RPC framing/lifecycle,
3. parsing provider responses,
4. normalizing to domain objects,
5. preserving unknown raw fields in metadata.

Authentication remains the responsibility of Codex CLI.

QuotaPilot must not store OpenAI credentials.

---

## 10. Provider failure strategy

Fallback sequence:

```text
live provider
   ↓ failure
cached snapshot
   ↓ unavailable
fallback capability definitions
```

The UI must expose the source:

```text
source = live | cache | fallback
```

Never present stale data as live.

---

## 11. Persistence

Use SQLite via `aiosqlite`.

Default path is provided by `platformdirs` (never a hardcoded home
directory), conceptually:

```text
$XDG_DATA_HOME/quotapilot/quotapilot.db
```

**Implemented in Phase 3** (see `src/quotapilot/history/`,
`docs/PHASE3_PERSISTENCE_CONTRACT.md`, and the corresponding
`docs/DECISIONS.md` entry — this supersedes the earlier `quota_snapshots`/
`model_catalog`/`routing_decisions`/`task_feedback` sketch that was written
before any provider existed to feed it):

The only canonical persistence input is
`UsageSnapshot` obtained from `await provider.capture_usage()` — never a
snapshot assembled from independent `get_account()`/`get_quota_pools()`/
`get_quota_bindings()` calls, which are not guaranteed mutually coherent.

Hybrid schema: normalized columns for common queryable fields, plus the
complete serialized snapshot/pool/binding for full-fidelity reconstruction
and preservation of unknown/future fields. Schema version `1`:

```sql
CREATE TABLE schema_version (version INTEGER NOT NULL);

CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    account_key TEXT,
    plan_name TEXT,
    captured_at TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE quota_pool_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    pool_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    kind TEXT NOT NULL,
    scope TEXT NOT NULL,
    used_fraction REAL,
    remaining_fraction REAL,
    starts_at TEXT,
    resets_at TEXT,
    window_seconds INTEGER,
    pool_json TEXT NOT NULL,
    FOREIGN KEY(snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
);

CREATE TABLE quota_binding_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    model_id TEXT NOT NULL,
    reasoning_effort TEXT,
    confidence TEXT NOT NULL,
    binding_json TEXT NOT NULL,
    FOREIGN KEY(snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
);
```

Raw provider account IDs are never persisted. When `AccountInfo.account_id`
is present, `account_key` stores a provider-scoped pseudonymous value:
`"sha256:" + sha256(provider + "\0" + account_id)`. The same value replaces
the structured account ID in `snapshot_json`; duplicate exact occurrences in
the canonical serialized copy are replaced too. This digest is stable for
local correlation but is not a secret. If no account ID exists, both values
remain `NULL`/`None`.

Every save calls `model_dump(mode="json", round_trip=True)` exactly once to
create one defensive canonical copy. Account pseudonymization, domain
re-validation, `snapshot_json`, child JSON, and every normalized column are
then derived from that copy before the write transaction opens. Runtime
metadata mutations therefore cannot make the parent and child rows disagree.
The normalized columns and child rows are query projections, not independent
sources of truth; `snapshot_json` is the reconstruction source. Reads always
go back through `UsageSnapshot.model_validate` — stored JSON is never trusted
as inherently valid.

Saving one snapshot (parent row + all pool rows + all binding rows) is one
SQLite transaction: all rows commit together or none do. Before writing,
persistence re-validates snapshot coherence (bindings reference only pools
in the same snapshot and contain no duplicate references; pool IDs are
unique; `captured_at` is timezone-aware; every pool and capability model has
the same provider as `account.provider`) even though the provider boundary is
already expected to guarantee it — defense in depth, not trust.

`schema_version` must hold exactly one integer row. `ensure_schema()` uses an
explicit `BEGIN IMMEDIATE`: a truly empty database gets the complete version-1
schema atomically, while any existing database must have the one supported
version and all required tables/columns. Missing, duplicate, malformed,
older, newer, or structurally incomplete version state raises
`DatabaseInitializationError` (no migration framework — add a
version-specific branch when version 2 is needed).

Public repository failures use the persistence taxonomy:
`DatabaseInitializationError`, `SnapshotSerializationError`,
`SnapshotWriteError`, and `SnapshotReadError`. SQLite exceptions are retained
only as chained causes, not exposed as the public error contract.

Do not over-design migrations beyond this. Introduce a heavier migration
mechanism only once schema evolution actually begins.

---

## 12. User configuration

Default location:

```text
~/.config/quotapilot/config.yaml
```

Initial schema:

```yaml
provider:
  default: openai-codex

budget:
  reserve_fraction: 0.10

  target:
    strategy: weighted-linear

  weekday_weights:
    monday: 1.0
    tuesday: 1.0
    wednesday: 1.0
    thursday: 1.0
    friday: 1.0
    saturday: 1.0
    sunday: 1.0

routing:
  policy: balanced

  allow:
    auto_recommendation: true

  escalation:
    enabled: true

  quota_pressure_weight: 0.35

ui:
  timezone: local
```

Configuration precedence:

1. CLI option
2. environment variable
3. user config
4. policy defaults
5. built-in defaults

---

## 13. Budget concepts

**Implemented in Phase 4.** The normative behavior, including conservative
missing-timing rules, deterministic calendar-day allocation, staleness, and
the provider-neutral report schema, is defined in
`docs/PHASE4_BUDGET_CONTRACT.md`. This section is a summary; the Phase 4
contract wins if an older example here is less precise.

Maintain separate concepts:

- actual usage `U(t)`
- expected usage `E(t)`
- reserve `R`

### 13.1 Linear pace

For a quota period starting at `t0` and resetting at `tr`:

```text
Pt = (t - t0) / (tr - t0)
```

Normalize `t`, `t0`, and `tr` to UTC instants before subtraction, then clamp
to `[0, 1]`. Local wall-clock arithmetic is not valid across DST transitions.

Expected usable consumption:

```text
E(t) = Pt * (1 - R)
```

Example:

```text
week progress = 50%
reserve = 10%
expected usage = 45%
```

### 13.2 Pace delta

```text
D = U(t) - E(t)
```

Interpretation:

- `D < 0`: under expected usage
- approximately zero: on pace
- `D > 0`: over expected usage

Default configurable states:

```text
VERY_UNDER: D < -0.20
UNDER:      -0.20 <= D < -0.07
ON_TRACK:   -0.07 <= D <= 0.07
OVER:        0.07 < D <= 0.20
CRITICAL:    D > 0.20
```

### 13.3 Daily budget

Remaining quota prefers `QuotaPool.remaining_fraction`; only when it is absent
may it be derived from the normalized `used_fraction`:

```text
Qr = 1 - U(t)
```

Available after reserve:

```text
Qa = max(0, Qr - R)
```

For remaining day weights `wi`:

```text
Bi = Qa * wi / sum(wj)
```

Today's suggested quota is `B_today`.

Phase 4 uses an explicit configured IANA timezone (default `UTC`). The current
calendar day counts as one full weighted day. A reset date is included unless
the reset occurs exactly at local midnight. Reset-only pools may receive a
daily allocation, but their expected usage and pace state remain `UNKNOWN`
because no start is fabricated.

Calendar weights are summed in O(1): complete weeks are multiplied by the
seven-day weight sum and only the remaining partial week is inspected.

### 13.4 Underuse matters

Example:

```text
reset in 12 hours
remaining quota = 40%
```

should lower quota pressure and permit stronger models more freely.

The objective is not merely conservation. It is useful value maximization over the subscription window.

---

## 14. Multi-window quotas

A model may simultaneously be constrained by multiple pools.

Example:

```text
5-hour remaining = 80%
weekly remaining = 5%
```

The weekly pool is the binding constraint.

Compute pressure for every applicable pool and initially use:

```text
effective_pressure = max(pool_pressures)
```

Do not average in v0.1.

Pools with insufficient pace semantics remain visible with `UNKNOWN` state and
`pressure=None`; they do not automatically override evaluable pools. Binding
ties are deterministic: pressure descending, remaining fraction ascending,
then pool ID ascending.

Suggested mapping from state to normalized quota pressure:

```text
VERY_UNDER -> 0.00
UNDER      -> 0.15
ON_TRACK   -> 0.35
OVER       -> 0.70
CRITICAL   -> 1.00
```

This mapping is QuotaPilot policy, not provider truth.

---

## 15. Task representation

```python
class TaskProfile(BaseModel):
    summary: str

    complexity: float
    ambiguity: float
    failure_cost: float
    verifiability: float
    expected_context_size: float
    latency_sensitivity: float

    tags: list[str] = []
```

All scores use `0.0 ... 1.0`.

v0.1 should support:

1. explicit CLI scores,
2. deterministic heuristic classification.

Do not require an LLM merely to choose another LLM.

Example:

```bash
quotapilot route \
  --complexity 0.7 \
  --failure-cost 0.8 \
  --verifiability 0.4
```

Suggested baseline complexity score:

```text
C =
0.30 * intrinsic_complexity
+ 0.20 * ambiguity
+ 0.20 * failure_cost
+ 0.15 * (1 - verifiability)
+ 0.15 * context_size
```

Clamp to `[0, 1]`.

---

## 16. Routing model

**Implemented in Phase 5.** `docs/PHASE5_ROUTING_CONTRACT.md` is normative;

this section retains the high-level model. The pure engine consumes
`TaskProfile + BudgetReport + CapabilitySet + RoutingPolicy` and never reads a
provider, database, environment, or clock. It excludes selectable models with
unknown power rather than inferring tiers from IDs, uses explicit neutral
fallbacks for unknown cost/latency, and surfaces every score component.

The capability floor is enforced before utility scoring. Unknown quota uses a
policy fallback while remaining labeled unknown. Effort is selected only from
an explicit normalized `effort_order`; escalation and alternatives are
advisory and capability-driven. Initial coefficients are deterministic and
explainable but not empirically calibrated.

Model utility concept:

```text
Sm = Qm - λCm - μLm
```

Where:

- `Qm`: estimated task suitability
- `Cm`: quota cost
- `Lm`: latency cost
- `λ`: quota-pressure coefficient
- `μ`: latency-sensitivity coefficient

Let:

```text
λ = λ0 * Pq
```

Therefore:

- low quota pressure makes stronger models easier to justify,
- high quota pressure favors lighter models.

Bundled routing policies:

- aggressive
- balanced (default)
- conservative

Policy controls:

- quota-pressure weight
- min/max model tier
- escalation behavior
- reserve preference

---

## 17. Escalation

The router supports escalation but does not require always starting weak.

Concept:

```text
initial recommendation
      ↓
attempt
      ↓
verification
      ↓
failure
      ↓
stronger recommendation
```

The actual ladder must be built from discovered account capabilities.

Never assume every account exposes the same models or effort levels.

Direct strong-model selection is permitted for tasks with:

- high ambiguity,
- high failure cost,
- large context/architecture scope,
- non-local debugging,
- security-sensitive analysis,
- repeated prior failure.

---

## 18. Recommendation object

```python
class ModelStep(BaseModel):
    model_id: str
    reasoning_effort: str | None = None


class ModelRecommendation(BaseModel):
    model_id: str
    reasoning_effort: str | None

    confidence: float

    quota_pressure: float
    task_complexity: float

    explanation: list[str]

    escalation_path: list[ModelStep]
    alternatives: list[ModelStep]
```

Example output:

```text
Recommended:
<model> / <effort>

Task complexity:
0.68

Quota pressure:
0.63

Why:
- weekly usage is ahead of target
- task is moderately complex
- output is easy to verify
- escalation is relatively inexpensive

Escalation:
<stronger model / effort>
```

---

## 19. CLI

Required commands:

```text
quotapilot budget
quotapilot status
quotapilot route
quotapilot history
quotapilot doctor
quotapilot config
quotapilot waybar
```

Every major command must support:

```text
--json
```

### 19.1 `quotapilot status`

Example:

```text
OpenAI Codex
Plan: <reported plan>
Source: live

5-hour quota
Used       41%
Remaining  59%
Reset      03:28

Weekly quota
Used       65%
Remaining  35%
Reset      Sep 23 09:59

Expected now
54%

Pace delta
+11%

State
OVER

Today's suggested budget
4.8%

Reserve
10%

Routing posture
CONSERVATIVE
```

### 19.2 `quotapilot route`

```bash
quotapilot route "Fix typo in README"
```

Example:

```text
Task class:
mechanical

Complexity:
0.12

Quota pressure:
0.61

Recommendation:
<light model> / <moderate effort>

Why:
- deterministic edit
- easy verification
- stronger model provides little expected benefit

Escalate if:
- requested change affects multiple subsystems
- first attempt fails
```

### 19.3 `quotapilot waybar`

JSON output:

```json
{
  "text": "QP 35%",
  "tooltip": "Weekly remaining: 35%\nPace: +11%\nState: OVER",
  "class": "over"
}
```

### 19.4 `quotapilot doctor`

Check:

- Codex executable exists
- Codex authentication appears available
- app-server can be started/reached
- expected account/rate-limit methods can be probed
- SQLite is writable
- config is valid
- clock/timezone handling works

Never print secrets.

---

## 20. Historical usage

When available, parse local Codex logs for:

- usage trend
- session activity
- model usage
- correlation between task class and consumption

Historical logs are supplemental.

Provider quota state remains authoritative for current remaining quota.

---

## 21. Fallback plan/capability definitions

Fallback definitions may include plan-name hints, but must carry provenance:

```yaml
verified_at: 2026-09-18
source: <URL or documentation identifier>
```

They are never authoritative over live discovery.

Do not bake current model catalogs deeply into code.

---

## 22. Security and privacy

QuotaPilot must:

- avoid storing provider access tokens,
- delegate authentication to official provider tooling,
- avoid browser-cookie extraction,
- keep local analysis local by default,
- redact account identifiers from logs,
- never execute arbitrary provider-returned shell commands.

Default:

```text
telemetry = disabled
```

No task text, repo name, or account metadata leaves the machine unless explicitly enabled by a future feature.

---

## 23. Testing strategy

### Unit tests

Cover:

- quota parsing
- fraction normalization
- pace calculations
- daily allocation
- reserve behavior
- multi-quota pressure
- task scoring
- model scoring
- routing
- escalation
- config merging
- unknown-model handling
- provider failure fallback

### Golden fixtures

Maintain fixtures such as:

```text
pro-normal.json
pro-weekly-low.json
plus-normal.json
go-normal.json
unknown-new-model.json
multiple-model-specific-limits.json
provider-response-missing-fields.json
```

Fixture names describe scenarios only. Tests must not require that those plan names always map to fixed limits.

### Integration tests

Live Codex tests may run only when explicitly enabled, for example:

```text
QUOTAPILOT_INTEGRATION=1
```

Normal CI must not require an authenticated Codex account.

### Algorithm acceptance examples

Case A:

```text
week progress = 50%
usage = 30%
reserve = 10%
```

Expected: low pressure / under pace.

Case B:

```text
week progress = 50%
usage = 75%
reserve = 10%
```

Expected: high pressure / over pace.

Case C:

```text
weekly remaining = 40%
reset in 8 hours
```

Expected: substantial underuse; strong-model penalty reduced.

Case D:

```text
5h remaining = 80%
weekly remaining = 5%
```

Expected: weekly pool dominates effective pressure.

---

## 24. v0.1 acceptance criteria

v0.1 is complete when:

1. `quotapilot status` can retrieve and display a real Codex quota state.
2. Multiple quota windows are normalized and displayed.
3. Reset times are rendered in local time.
4. Snapshots persist in SQLite.
5. Weekly expected pace is calculated.
6. Daily suggested usage is calculated.
7. Reserve quota is respected.
8. Underuse is detected.
9. Overuse is detected.
10. `quotapilot route` gives deterministic recommendations.
11. Recommendation changes with quota pressure.
12. Recommendation changes with task complexity.
13. Unknown models do not crash the program.
14. Provider failures degrade to cache/fallback clearly.
15. `--json` works for status and route.
16. `quotapilot waybar` emits valid JSON.
17. Core algorithms have unit coverage.
18. CI works without provider credentials.

---

## 25. Implementation phases

### Phase 0 — repository bootstrap

Create:

- `pyproject.toml`
- src layout
- pytest
- ruff
- pyright/mypy configuration
- GitHub Actions
- basic README

No live provider integration yet.

### Phase 1 — domain layer

Implement:

- AccountInfo
- AIModel
- CapabilitySet
- QuotaPool
- QuotaBinding
- UsageSnapshot

Keep domain provider-independent.

### Phase 2 — OpenAI Codex adapter

Implement:

- app-server lifecycle
- JSON-RPC transport
- account information retrieval
- rate-limit retrieval
- parser/normalizer
- fixture capture/sanitization
- parser tests

Do not implement budget/routing yet.

### Phase 3 — snapshot persistence

Implement SQLite repository and snapshot storage.

### Phase 4 — budget engine

Implement:

- window progress
- expected consumption
- pace delta
- budget state
- reserve
- daily allocation
- multi-window pressure

Also expose `quotapilot budget` and `quotapilot budget --json` over the latest
persisted snapshot. See `docs/PHASE4_BUDGET_CONTRACT.md`.

Prefer pure functions.

### Phase 5 — routing engine

Implemented:

- TaskProfile
- complexity scoring
- model metadata
- model utility
- recommendation
- escalation ladder

Also exposes `quotapilot route` and `quotapilot route --json`. See
`docs/PHASE5_ROUTING_CONTRACT.md`.


### Phase 5.5 — Capability Metadata & Routing Calibration

Detailed implementation contract: `docs/PHASE5_5_CALIBRATION_CONTRACT.md`

Implemented. Phase 5.5 enriches discovered model capabilities with versioned,
provenance-aware routing metadata and evaluates routing policy against
deterministic synthetic calibration scenarios. Model-specific knowledge stays
in `policies/model_profiles/`, outside the provider-independent router.

Enrichment uses exact provider/model-ID matching and fills only absent fields.
Existing normalized capability values win. Only fresh profiles are applied;
stale and unknown-freshness matches remain observable but cannot make a model
routable. Provenance is carried in model metadata and surfaced in route/model
output. The pure enrichment and calibration paths perform no network or
persistence I/O.

`quotapilot models` inspects enriched metadata from the latest snapshot, and
`quotapilot calibrate evaluate` replays the versioned scenario suite through
the unchanged Phase 5 Routing Engine. The profile and scenario files are
Git-reviewable root artifacts and are packaged into wheels. See
`docs/PHASE5_5_CALIBRATION_CONTRACT.md`.

This phase remains advisory. It does not execute model recommendations.

### Phase 6 — Controlled Execution & Agent Integration

Implemented. `src/quotapilot/execution/` adds strict execution plans/results,
a separate authorization policy, a pure planner, bounded retry/escalation, and
a provider-neutral adapter protocol. `ExecutionService` composes the existing
route stack with a coherent live usage capture before every real attempt; it
invalidates a plan on material quota, capability, effort, profile-freshness,
or recommendation change.

`quotapilot execute TASK --dry-run [--json]` renders a privacy-safe plan and
never invokes either the provider or Codex. Real execution defaults to
`always_confirm`, and a materially different escalation plan requires new
approval. The initial Codex CLI adapter uses structured subprocess arguments,
stdin task delivery, an explicit working directory, `workspace-write`
sandboxing, a mandatory timeout, process cleanup, and credential-redacted
bounded output tails. It persists neither raw task text nor agent output.

Retry is same model/effort and is limited to explicitly configured transient
failure classes. Escalation is distinct, follows only the Phase 5 advisory
path, rechecks quota/capabilities first, and remains bounded by total attempts.
Authentication and user cancellation never escalate. See
`docs/PHASE6_EXECUTION_CONTRACT.md` for the complete boundary and verified
Codex CLI 0.155.0 invocation.

The previously sketched `status`, `doctor`, and `history` dashboard commands
remain outside this phase; their absence does not alter the execution safety
boundary.

### Phase 7 — Productization, Observability & Release Readiness

Implemented. `src/quotapilot/config/` provides strict optional YAML
configuration at the platform-resolved user config directory. Existing
`BudgetConfig`, `RoutingPolicy`, and `ExecutionPolicy` remain the authoritative
policy schemas. Effective precedence is CLI, selected `QUOTAPILOT_*`
environment overrides, user config, policy defaults, then built-in defaults;
`quotapilot config show` exposes the winning source without enumerating the
environment.

`StatusService` composes the latest coherent snapshot, the Phase 4 Budget
Engine, and Phase 5.5 capability enrichment into a privacy-safe `StatusReport`.
`quotapilot status` defaults to persisted state and can explicitly request one
live refresh; a failed refresh preserves and labels the persisted fallback.
`quotapilot waybar` is deliberately persisted-only, emits one valid JSON object
for success or failure, and never captures live state or executes a model.

`quotapilot doctor` emits structured PASS/WARN/FAIL/SKIP checks for strict
config, database/schema access, Codex availability/version/auth/app-server,
profiles/freshness/routability, optional explicit provider capture, Waybar, and
the execution adapter. It discards authentication command output and never
enumerates environment secrets. No execution-history command was added because
Phase 6 intentionally persists no execution audit.

Version `0.1.0` comes from package metadata. Wheel/sdist builds bundle exact
model profiles and calibration scenarios, and CI verifies pytest, Ruff,
Pyright, build, installed CLI entry points, and installed package resources.
See `docs/PHASE7_PRODUCTIZATION_CONTRACT.md` and
`docs/RELEASE_CHECKLIST.md`.

### Phase 8 — observation period

Run recommendation-only mode and record:

- recommendation
- actual model chosen
- success/failure
- escalation
- subjective adequacy

Do not expand the existing policy-gated execution boundary during observation.

---

## 26. Immediate first vertical slice

Before routing, demonstrate:

```text
Codex
 ↓
rate-limit/account data
 ↓
QuotaPool normalization
 ↓
basic status rendering
```

Target demonstration:

```text
$ quotapilot status

OpenAI Codex

Weekly
Used       XX%
Remaining  YY%
Reset      ...

Source     live
```

Then add budget math.

---

## 27. Architectural dependency boundary

Allowed direction:

```text
CLI
 ↓
Services
 ↓
Budget / Routing
 ↓
Domain

Providers
 ↓
Domain

Persistence
 ↓
Domain
```

Forbidden examples:

```text
Domain -> OpenAI
Budget -> Codex RPC
Routing -> SQLite
Provider -> CLI
```

---

## 28. Agent-development protocol

This repository is intentionally designed for handoff between Claude Code and Codex.

Before making changes, an agent must read in order:

1. `docs/TECHNICAL_DESIGN.md`
2. `docs/DECISIONS.md`
3. `docs/HANDOFF.md`
4. its agent-specific root instruction file (`CLAUDE.md` or `AGENTS.md`)

At the end of each meaningful implementation session:

1. run relevant tests,
2. update `docs/HANDOFF.md`,
3. append architectural decisions to `docs/DECISIONS.md` if needed,
4. list changed files and test results,
5. leave a concrete next action for the next agent.

`HANDOFF.md` is mutable current state.

`DECISIONS.md` is append-oriented design history.

`TECHNICAL_DESIGN.md` is the canonical product/architecture specification and should only change when the design itself changes.

---

## 29. Engineering philosophy

Prefer:

```text
boring
typed
deterministic
observable
testable
replaceable
```

over:

```text
clever
LLM-dependent
opaque
provider-hardcoded
```

Core quota mathematics must not require an LLM.

---

## 30. Definition of done for an implementation PR

Each implementation PR should include:

- tests,
- type annotations for changed public code,
- documentation for changed public behavior,
- no unrelated refactors,
- no credentials,
- fixture coverage for provider parsing,
- backward-compatible config changes where practical.

If live provider behavior differs from this specification:

1. preserve a sanitized real fixture,
2. document the discrepancy,
3. adapt the provider boundary,
4. do not invent undocumented semantics merely to satisfy the design.

---

## 31. Success criterion

QuotaPilot succeeds when the user no longer has to default to:

> Use the strongest model.

Instead, the decision becomes visible as:

```text
Task difficulty
      +
Current quota
      +
Time until reset
      +
Reserved capacity
      +
Expected value of stronger reasoning
      ↓
Recommended model and effort
```

while preserving human control.

---

## 32. Phase 8.1 desktop localization and provider status

The GUI uses Qt translation infrastructure (`qsTranslate`, `QTranslator`, and
packaged TS/QM catalogs). `appearance.language` is strict central configuration
with `system`, `en`, and `ja`; unsupported system locales fall back to English.
Only the language preference is applied live through QML retranslation.

Provider connection inspection is a provider-boundary operation returning a
small provider-neutral typed result. A service combines it with the existing
privacy-safe status report for GUI display. It exposes no account identity,
plan inference, credentials, or raw response data and runs on the existing GUI
worker boundary.
