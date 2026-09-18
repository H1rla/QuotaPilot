# QuotaPilot Development Handoff

> Shared current-state window for Claude Code and Codex. Read the technical
> design and decision log before continuing.

## Current state

- Date: 2026-09-18
- Last agent: Claude Code
- Current phase: **Phase 3 (snapshot persistence) complete**
- Phase 3 readiness: **COMPLETE**
- Phase 4 readiness: not started; provider + persistence boundary now stable
- Dependency direction: `providers -> domain`, `history -> domain`,
  `services -> providers, history, domain`; no domain import of provider or
  persistence code, no `quotapilot.history` import of any provider package
  (verified by inspection)

`OpenAICodexProvider.capture_usage() -> UsageSnapshot` is the only canonical
persistence input. `SnapshotService.capture_and_store()` is the only place
that calls both a provider and a repository.

## Phase 3 work (this session)

- Added `src/quotapilot/history/` — `repository.py` (`SnapshotRepository`
  Protocol, provider-independent), `sqlite.py`
  (`SqliteSnapshotRepository`), `migrations.py` (`ensure_schema`,
  `CURRENT_SCHEMA_VERSION = 1`), `errors.py` (`PersistenceError` and
  `DatabaseInitializationError`/`SnapshotCoherenceError`/
  `SnapshotSerializationError`/`SnapshotWriteError`/`SnapshotReadError`).
- Added `src/quotapilot/services/snapshot.py` — `SnapshotService`,
  `StoredSnapshot`.
- Schema (version 1): `snapshots` (parent row + full `snapshot_json`),
  `quota_pool_samples`, `quota_binding_samples` (both `ON DELETE CASCADE`),
  `schema_version` (single row). Hybrid design: normalized columns for
  future queries, full serialized JSON for lossless reconstruction.
- `save_snapshot()` is one transaction (parent + all pool rows + all
  binding rows commit or none do) and re-validates coherence
  (bindings reference only same-snapshot pools; `captured_at`
  timezone-aware; pool `provider` matches `account.provider`) before
  opening it — defense in depth on top of the provider's own guarantee.
- Serialization is defensive: writes go through
  `model_dump(mode="json", round_trip=True)`, never a live `metadata`
  reference; reads always re-validate through `UsageSnapshot.model_validate`
  — stored JSON is never trusted blindly.
- Default DB path via `platformdirs` (`$XDG_DATA_HOME/quotapilot/quotapilot.db`
  or platform equivalent) — never a hardcoded home directory.
- Added minimal CLI: `quotapilot snapshot capture` / `quotapilot snapshot
  latest` (`src/quotapilot/cli/snapshot.py`). Prints provider/plan/pool
  summary only — no `account_id`, no `metadata` envelopes.
- Updated `docs/TECHNICAL_DESIGN.md` §11 to reflect the actual implemented
  schema (superseding the earlier, pre-provider `quota_snapshots`/
  `model_catalog`/`routing_decisions` sketch). Appended a `docs/DECISIONS.md`
  entry recording every persistence-layer decision, including the
  `account_key` privacy reasoning and the UTC-normalization-for-sorting
  rationale.
- Did **not** touch budget/pace/routing/Waybar — untouched, per phase
  ordering and this session's explicit scope guard.

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

- Offline/default pytest: **161 passed, 5 skipped** (the 5 skips are the
  opt-in authenticated integration suite).
- Ruff: **All checks passed**.
- Pyright: **0 errors, 0 warnings, 0 informations**.
- CLI: `quotapilot --help` and `quotapilot snapshot --help` both work.
- Live integration (`QUOTAPILOT_INTEGRATION=1`): **5 passed** — includes a
  new live capture -> temporary SQLite DB -> save -> reload -> compare test
  (`test_live_capture_save_reload_round_trip`), confirmed against the real
  authenticated account. No credential, account identifier, or raw
  transport response was printed.

Normal tests remain fully offline: persistence tests use `tmp_path`
temp-file SQLite databases and either hand-built domain objects or a fake
stdio `codex app-server` peer (never the real binary or network). Live
tests still require `QUOTAPILOT_INTEGRATION=1`.

## Privacy/security state

- `UsageSnapshot` remains the maximum information boundary allowed into
  persistence — `quotapilot.history` never imports a provider package and
  never sees a raw RPC/transport response, only already-sanitized domain
  objects.
- `account_key` in the `snapshots` table stores `AccountInfo.account_id`
  verbatim (nullable) — this is the already-sanctioned, never-redacted
  structured field, not a new exposure; see the `docs/DECISIONS.md` entry
  for the full reasoning. The `raw_observation` metadata envelope's own
  copy of the account id remains redacted, as before.
- No credentials, tokens, cookies, or raw transport payloads are ever
  constructed or read by `quotapilot.history`.

## Known risks / deferred decisions (carried forward + new)

- Long-lived vs. ephemeral `codex app-server` lifecycle remains
  deliberately undecided (Phase 2.1 note, unchanged).
- `metadata` dicts are only shallowly immutable at the domain layer;
  persistence defends against this by always serializing through
  `model_dump(...)` rather than holding live references — but any *other*
  future consumer of a `UsageSnapshot` still needs to respect this
  convention itself.
- No migration framework exists — only a single schema version (1) with a
  clear-failure path for any other version. The first real migration will
  need its own hand-written upgrade branch in `migrations.py`.
- `account/usage/read` (token-usage history) still has no domain mapping
  and therefore no persistence path — unchanged from Phase 2.1.
- The live account still only exercises the single-window,
  no-model-scoped-pool rate-limit shape end-to-end; multi-window/
  model-scoped/no-window persistence paths are covered by
  hand-built-snapshot and fake-peer-driven tests, not a live capture.

## Next task

Phase 4 (budget engine — pace, reserve, daily allocation, multi-window
pressure) may begin only when explicitly requested. It should consume
`SnapshotRepository.get_latest_snapshot()`/`list_snapshots()` for historical
pace calculations; it must not reach into providers or persistence
internals directly, and must not be started as a side effect of a
persistence-focused session.
