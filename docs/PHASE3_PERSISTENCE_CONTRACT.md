
# QuotaPilot Phase 3 Persistence Contract

## 1. Purpose

Phase 3 introduces persistence for coherent provider snapshots.

The persistence layer must store enough information to support:

* historical quota analysis,
* future budget calculations,
* schema evolution,
* parser improvements,
* debugging,
* provider-data reinterpretation.

Phase 3 must NOT implement:

* budget calculations,
* pace calculations,
* routing,
* model recommendations,
* automatic model switching,
* Waybar integration.

---

## 2. Persistence boundary

The only canonical persistence input is:

```python
UsageSnapshot
```

obtained from:

```python
await provider.capture_usage()
```

Do not persist a snapshot assembled from independent calls to:

```python
get_account()
get_quota_pools()
get_quota_bindings()
```

because those calls are not guaranteed to represent one coherent observation.

Canonical flow:

```text
Provider
   ↓
capture_usage()
   ↓
UsageSnapshot
   ↓
SnapshotRepository
   ↓
SQLite
```

---

## 3. Persistence principles

The persistence layer must preserve:

1. normalized domain state,
2. capture timestamp,
3. quota-pool state,
4. quota bindings,
5. account/capability state,
6. sanitized raw provider observation,
7. provenance metadata.

The persistence layer must not:

* store credentials,
* store browser cookies,
* store authentication headers,
* assume current OpenAI schema is permanent,
* mutate domain objects,
* silently discard unknown metadata.

---

## 4. Defensive serialization

Current domain models are frozen at the field level, but nested metadata mappings are only shallowly immutable.

Therefore persistence must serialize through a defensive boundary.

Preferred strategy:

```python
snapshot.model_dump(
    mode="json",
    round_trip=True,
)
```

or equivalent Pydantic serialization.

Do not store references to mutable runtime dictionaries.

Persistence must operate on serialized/copied values.

---

## 5. SQLite

Use SQLite via `aiosqlite`.

Default database location:

```text
$XDG_DATA_HOME/quotapilot/quotapilot.db
```

resolved through `platformdirs`.

The application must create parent directories automatically.

SQLite settings should favor correctness over premature tuning.

Recommended initialization:

```sql
PRAGMA foreign_keys = ON;
```

WAL may be considered, but is not required for Phase 3 unless justified by implementation needs.

---

## 6. Repository interface

Introduce a provider-independent repository protocol.

Example:

```python
class SnapshotRepository(Protocol):
    async def save_snapshot(
        self,
        snapshot: UsageSnapshot,
    ) -> int:
        ...

    async def get_snapshot(
        self,
        snapshot_id: int,
    ) -> UsageSnapshot | None:
        ...

    async def get_latest_snapshot(
        self,
        provider: str | None = None,
    ) -> UsageSnapshot | None:
        ...

    async def list_snapshots(
        self,
        *,
        provider: str | None = None,
        limit: int = 100,
    ) -> tuple[UsageSnapshot, ...]:
        ...
```

The repository interface must remain independent of OpenAI/Codex.

---

## 7. Schema strategy

Use normalized relational columns for common queryable fields, while preserving the full sanitized serialized snapshot.

Recommended design:

### snapshots

```sql
CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    provider TEXT NOT NULL,
    account_key TEXT,
    plan_name TEXT,

    captured_at TEXT NOT NULL,

    snapshot_json TEXT NOT NULL,

    created_at TEXT NOT NULL
);
```

### quota_pool_samples

```sql
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

    FOREIGN KEY(snapshot_id)
        REFERENCES snapshots(id)
        ON DELETE CASCADE
);
```

### quota_binding_samples

```sql
CREATE TABLE quota_binding_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    snapshot_id INTEGER NOT NULL,

    model_id TEXT NOT NULL,
    reasoning_effort TEXT,
    confidence TEXT NOT NULL,

    binding_json TEXT NOT NULL,

    FOREIGN KEY(snapshot_id)
        REFERENCES snapshots(id)
        ON DELETE CASCADE
);
```

This provides:

```text
fast common queries
        +
full-fidelity reconstruction
```

---

## 8. Why store both relational columns and JSON

Normalized columns support future queries such as:

```text
weekly usage over time
reset-time progression
model-specific quota pressure
```

Full JSON preserves:

* unknown metadata,
* provenance,
* future provider fields,
* currently-unused raw observations.

Do not choose only one.

---

## 9. Serialization format

Use JSON.

Requirements:

* UTF-8,
* deterministic enough for testing,
* datetime represented in ISO 8601,
* tuples/lists round-trip safely,
* unknown metadata preserved.

When reading stored snapshots, validate again through domain models.

Do not trust persisted JSON as inherently valid.

---

## 10. Account identity

Do not persist raw sensitive account identifiers unless required.

Preferred approach:

```text
provider-scoped stable pseudonymous key
```

If a provider exposes an account ID and the current redaction layer already sanitizes it, do not reverse that sanitization.

For Phase 3, nullable `account_key` is acceptable.

Do not invent account identity if none is safely available.

---

## 11. Transaction semantics

Saving one `UsageSnapshot` must be atomic.

The following must either all succeed or all roll back:

```text
snapshot row
quota_pool_samples
quota_binding_samples
```

Use one SQLite transaction.

There must never be a committed snapshot row with only half its child rows written.

---

## 12. Snapshot coherence validation

Before persistence:

* every `QuotaBinding.quota_pool_ids` entry must reference a pool contained in the same snapshot,
* captured_at must be timezone-aware,
* snapshot provider identity must be internally consistent.

The provider already performs coherence checks.

Persistence should still validate enough to protect the database boundary.

---

## 13. Duplicate snapshots

Phase 3 does not need aggressive deduplication.

Every successful capture may be stored as a historical observation.

Do not use:

```text
UNIQUE(snapshot_json)
```

or equivalent.

Repeated identical state at different times is meaningful historical data.

---

## 14. Database migrations

Introduce a minimal schema-version mechanism now.

Recommended:

```sql
CREATE TABLE schema_version (
    version INTEGER NOT NULL
);
```

or equivalent metadata table.

Initial version:

```text
1
```

Do not introduce a heavy migration framework unless required.

Migration behavior must be testable.

---

## 15. Repository implementation

Suggested modules:

```text
src/quotapilot/history/
├── __init__.py
├── repository.py
├── sqlite.py
└── migrations.py
```

or equivalent structure consistent with the existing repository.

Suggested responsibilities:

### repository.py

Provider-independent repository protocol.

### sqlite.py

SQLite implementation.

### migrations.py

Database initialization and schema upgrades.

---

## 16. Snapshot service

Introduce a thin service layer if useful:

```text
src/quotapilot/services/snapshot.py
```

Responsibilities:

```text
provider.capture_usage()
        ↓
repository.save_snapshot()
```

Possible interface:

```python
class SnapshotService:
    async def capture_and_store(self) -> StoredSnapshot:
        ...
```

Do not put budget logic here.

---

## 17. CLI scope

Phase 3 may add only minimal persistence-facing commands if useful.

Acceptable:

```text
quotapilot snapshot capture
quotapilot snapshot latest
```

or equivalent.

However CLI expansion is optional.

Core Phase 3 success is the repository implementation and tests.

Do not implement historical analytics yet.

---

## 18. Failure behavior

Persistence failures must not corrupt existing data.

Introduce generic persistence errors such as:

```python
class PersistenceError(Exception):
    ...
```

Possible subclasses:

```text
DatabaseInitializationError
SnapshotSerializationError
SnapshotWriteError
SnapshotReadError
```

Do not leak SQLite internals unnecessarily into upper layers.

---

## 19. Metadata preservation

The following data must survive save/load round-trip:

* quota provenance,
* capability provenance,
* unknown fields,
* `raw_observation`,
* `model_list_pages`,
* redaction metadata,
* provider-specific unknown structures.

Tests must explicitly verify this.

---

## 20. Privacy requirements

Before writing serialized snapshot JSON:

* use already-sanitized provider observation,
* do not reintroduce raw provider payloads from transport,
* do not persist secrets,
* do not persist credentials,
* do not persist unredacted account IDs.

Persistence must treat the `UsageSnapshot` domain object as the maximum allowed information boundary.

Do not reach back into raw RPC transport responses.

---

## 21. Test requirements

Add tests for:

### Database creation

Fresh database initializes correctly.

### Save/load round-trip

```text
UsageSnapshot
→ SQLite
→ UsageSnapshot
```

must preserve semantics.

### Multiple pools

All pools survive.

### Multiple bindings

All bindings survive.

### Unknown metadata

Unknown nested metadata survives.

### Raw observation

Sanitized raw observation survives.

### Transaction rollback

Failure while writing children must leave no partial snapshot.

### Foreign keys

Child rows cannot exist without snapshot.

### Latest snapshot

Latest capture is returned correctly.

### Provider filtering

If implemented, latest/list filtering works.

### Duplicate state

Identical snapshots with different capture times may both exist.

### Datetimes

Timezone-aware timestamps round-trip correctly.

### Schema version

Fresh initialization and no-op reopen work correctly.

---

## 22. Integration test

Add an optional integration test:

```text
live capture
→ temporary SQLite database
→ save
→ reload
→ semantic comparison
```

Guard behind:

```text
QUOTAPILOT_INTEGRATION=1
```

Normal CI remains offline.

---

## 23. Acceptance criteria

Phase 3 is complete when:

1. `capture_usage()` output can be persisted.
2. Persistence is atomic.
3. Snapshot can be reconstructed.
4. All normalized quota pools survive round-trip.
5. All quota bindings survive round-trip.
6. Sanitized raw observation survives round-trip.
7. Unknown metadata survives round-trip.
8. No secrets are persisted.
9. Database path uses platformdirs.
10. Schema versioning exists.
11. Normal test suite is offline.
12. CI remains credential-free.
13. Live capture → save → reload works when integration tests are enabled.
14. No budget/routing logic was implemented.

---

## 24. Phase 3 completion boundary

After Phase 3:

```text
Provider
   ↓
capture_usage()
   ↓
UsageSnapshot
   ↓
SQLite history
```

Only after this boundary is stable should Phase 4 begin:

```text
historical/current snapshot
        ↓
Budget Engine
        ↓
pace / reserve / daily allocation
```
