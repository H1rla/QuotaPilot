# QuotaPilot Development Handoff

> Shared current-state window for Claude Code and Codex. Read the technical
> design and decision log before continuing.

## Current state

- Date: 2026-09-18
- Last agent: Codex
- Current phase: **Phase 3.1 persistence stabilization complete**
- Phase 2 readiness: **COMPLETE**
- Phase 3.1 readiness: **COMPLETE**
- Phase 4 readiness: **READY**, but not started
- Dependency direction remains `providers -> domain`, `history -> domain`,
  `services -> providers + history + domain`

`OpenAICodexProvider.capture_usage() -> UsageSnapshot` remains the only
canonical capture boundary. `SnapshotService.capture_and_store()` is the only
production path that calls both a provider and a repository. No budget,
reserve, pace, scoring, or routing logic was added in Phase 3.1.

## Phase 3.1 stabilization

### Privacy-safe account identity

- Raw `AccountInfo.account_id` values are never written to SQLite.
- A present ID becomes
  `"sha256:" + sha256(provider + "\0" + account_id)` for local correlation.
  This digest is provider-scoped, stable, one-way, and explicitly not secret.
- `snapshots.account_key` and the structured account ID in `snapshot_json`
  contain the pseudonym; exact duplicate occurrences in the canonical copy are
  replaced before any parent/child JSON is built.
- Missing IDs remain `NULL`/`None`.
- The input `UsageSnapshot` and its nested metadata are not mutated.

### Canonical persistence representation

- Each save validates the input and crosses one defensive
  `model_dump(mode="json", round_trip=True)` boundary.
- Privacy transformation, domain re-validation, parent JSON, pool/binding
  JSON, and normalized SQL columns all derive from that same copied state.
- Relational rows are query projections; `snapshot_json` is the reconstruction
  source of truth.
- Tests mutate nested runtime metadata after the copy boundary and after save;
  persisted parent/child data remains mutually consistent and unchanged.

### Schema and error integrity

- Fresh initialization is one `BEGIN IMMEDIATE` transaction.
- Existing schema state requires exactly one integer version row plus every
  required version-1 table/column.
- Empty, duplicate, mixed, malformed, older/newer, missing-table, and
  missing-column states fail as `DatabaseInitializationError`.
- Public operations now preserve typed persistence errors:
  `DatabaseInitializationError`, `SnapshotSerializationError`,
  `SnapshotWriteError`, and `SnapshotReadError`. Internal SQLite errors are
  chained causes rather than the public contract.
- Rollback/cleanup paths leave the repository usable after handled failures.

### Coherence and SQLite behavior

- Persistence rejects model/pool provider mismatches, duplicate pool IDs,
  dangling bindings, duplicate pool references within one binding, and naive
  capture timestamps before write transaction mutation.
- Foreign keys are enabled and verified on every connection.
- Tests exercise actual orphan rejection and `ON DELETE CASCADE`.
- Latest ordering remains `captured_at DESC, id DESC`; equal timestamps are
  deterministic. Unknown provider filters return an empty result.
- Unknown nested metadata, capability/quota provenance, raw observation, and
  page-level `model_list_pages` fields survive save/reload.

## Verification

Commands run from the repository root:

```bash
uv run pytest
uv run ruff check .
uv run pyright
uv run quotapilot --help
QUOTAPILOT_INTEGRATION=1 uv run pytest tests/integration/
```

Results:

- Offline/default pytest: **185 passed, 5 skipped**. The skipped tests are the
  explicitly gated authenticated integration suite.
- Ruff: **All checks passed**.
- Pyright: **0 errors, 0 warnings, 0 informations**.
- CLI: `quotapilot --help` succeeded.
- Live integration: **5 passed**. The live capture -> temporary SQLite -> save
  -> privacy-safe reload comparison passed; no credential or raw account value
  was printed.

Normal tests remain offline. Live tests still require
`QUOTAPILOT_INTEGRATION=1` and use the already-authenticated Codex CLI.

## Privacy/security state

- `UsageSnapshot` remains the maximum allowed persistence input;
  `quotapilot.history` has no provider/RPC/authentication imports.
- Provider-side redaction remains unchanged and runs before raw-observation
  metadata enters the domain snapshot.
- Persistence adds only the structured account-ID pseudonymization described
  above; it never reaches back into transport, credentials, browser state, or
  auth files.
- Regression tests inspect `account_key`, full `snapshot_json`, `pool_json`,
  and `binding_json` and prove the raw account ID is absent.

## Remaining risks / deferred decisions

- The version mechanism is intentionally minimal. The first real schema change
  still needs an explicit version-2 migration branch.
- `metadata` dictionaries remain shallowly mutable in memory; the persistence
  boundary is protected, but other future consumers must still treat them as
  read-only or copy defensively.
- A repository-loaded snapshot contains the persisted pseudonymous account ID,
  not the original provider account ID. Provider captures remain the source for
  new observations; loaded historical snapshots should not be re-saved as new
  captures.
- Long-lived versus ephemeral `codex app-server` lifecycle remains deferred.
- `account/usage/read` token history still has no domain/persistence mapping.
- Live provider coverage still reflects the shapes available to the current
  authenticated account; synthetic tests cover multi-window/model-specific and
  corrupt-storage cases.

## Next task

Phase 4 (Budget Engine) may begin when explicitly requested. It should consume
the repository's domain snapshots without importing provider RPC or SQLite
internals. Do not reassemble captures from independent provider getters.
