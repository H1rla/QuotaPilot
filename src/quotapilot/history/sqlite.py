"""SQLite-backed `SnapshotRepository` implementation.

```text
UsageSnapshot
    v (defensive serialization: model_dump(mode="json", round_trip=True))
snapshot_json / pool_json / binding_json
    v (one transaction)
snapshots / quota_pool_samples / quota_binding_samples
```

Provider-independent: this module imports only `quotapilot.domain` and
`quotapilot.history` — never a provider package. Persistence never reaches
back into raw RPC/transport responses; `UsageSnapshot` (already sanitized
by the provider boundary) is the maximum information boundary allowed in.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite
import platformdirs
from pydantic import ValidationError

from quotapilot.domain.quota import QuotaBinding, QuotaPool
from quotapilot.domain.usage import UsageSnapshot

from .errors import (
    DatabaseInitializationError,
    SnapshotCoherenceError,
    SnapshotReadError,
    SnapshotSerializationError,
    SnapshotWriteError,
)
from .migrations import ensure_schema

_APP_NAME = "quotapilot"


def default_database_path() -> Path:
    """`$XDG_DATA_HOME/quotapilot/quotapilot.db` (or the platform equivalent).

    Never hardcodes a user's home directory — resolved via `platformdirs`.
    """
    return Path(platformdirs.user_data_dir(_APP_NAME)) / f"{_APP_NAME}.db"


def _to_utc_isoformat(value: datetime) -> str:
    """Normalize to UTC before formatting so stored timestamps are both
    human-readable and lexicographically sortable regardless of which
    timezone offset a provider originally captured in."""
    return value.astimezone(UTC).isoformat()


class SqliteSnapshotRepository:
    """`SnapshotRepository` backed by a local SQLite database via `aiosqlite`.

    Opens and closes a connection per call rather than holding one open —
    simple and correct for Phase 3's usage pattern (infrequent captures);
    revisit only if profiling ever shows it matters.
    """

    def __init__(self, database_path: str | Path | None = None) -> None:
        self._database_path = (
            Path(database_path) if database_path is not None else default_database_path()
        )

    @property
    def database_path(self) -> Path:
        return self._database_path

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator[aiosqlite.Connection]:
        try:
            self._database_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise DatabaseInitializationError(
                f"failed to create database directory {self._database_path.parent}"
            ) from exc

        try:
            conn = await aiosqlite.connect(self._database_path)
        except Exception as exc:
            raise DatabaseInitializationError(
                f"failed to open database at {self._database_path}"
            ) from exc

        try:
            await ensure_schema(conn)
            yield conn
        finally:
            await conn.close()

    @staticmethod
    def _check_coherence(snapshot: UsageSnapshot) -> None:
        """Re-validate what the provider is already expected to guarantee
        (design's `UsageProvider.capture_usage` contract) at the
        persistence boundary too, rather than trusting it silently."""
        if snapshot.captured_at.tzinfo is None:
            raise SnapshotCoherenceError("captured_at must be timezone-aware")

        pool_ids = {pool.id for pool in snapshot.quota_pools}
        for binding in snapshot.quota_bindings:
            unknown = [pid for pid in binding.quota_pool_ids if pid not in pool_ids]
            if unknown:
                raise SnapshotCoherenceError(
                    f"binding for model {binding.model_id!r} references pool id(s) "
                    f"{unknown!r} not present in this snapshot's quota_pools"
                )

        inconsistent = [
            pool.id for pool in snapshot.quota_pools if pool.provider != snapshot.account.provider
        ]
        if inconsistent:
            raise SnapshotCoherenceError(
                f"pool(s) {inconsistent!r} have provider != account.provider "
                f"({snapshot.account.provider!r})"
            )

    @staticmethod
    def _serialize(model: UsageSnapshot | QuotaPool | QuotaBinding) -> dict[str, Any]:
        try:
            return model.model_dump(mode="json", round_trip=True)
        except Exception as exc:  # noqa: BLE001 - any serialization failure is our error, not the caller's
            raise SnapshotSerializationError(f"failed to serialize {type(model).__name__}") from exc

    async def _insert_snapshot_row(
        self, conn: aiosqlite.Connection, snapshot: UsageSnapshot, snapshot_json: dict[str, Any]
    ) -> int:
        cursor = await conn.execute(
            """
            INSERT INTO snapshots
                (provider, account_key, plan_name, captured_at, snapshot_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.account.provider,
                snapshot.account.account_id,
                snapshot.account.plan_name,
                _to_utc_isoformat(snapshot.captured_at),
                json.dumps(snapshot_json),
                _to_utc_isoformat(datetime.now(UTC)),
            ),
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid

    async def _insert_pool_samples(
        self, conn: aiosqlite.Connection, snapshot_id: int, pools: tuple[QuotaPool, ...]
    ) -> None:
        for pool in pools:
            pool_json = self._serialize(pool)
            await conn.execute(
                """
                INSERT INTO quota_pool_samples
                    (snapshot_id, pool_id, provider, kind, scope, used_fraction,
                     remaining_fraction, starts_at, resets_at, window_seconds, pool_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    pool.id,
                    pool.provider,
                    pool.kind,
                    pool.scope,
                    pool.used_fraction,
                    pool.remaining_fraction,
                    _to_utc_isoformat(pool.starts_at) if pool.starts_at is not None else None,
                    _to_utc_isoformat(pool.resets_at) if pool.resets_at is not None else None,
                    pool.window_seconds,
                    json.dumps(pool_json),
                ),
            )

    async def _insert_binding_samples(
        self, conn: aiosqlite.Connection, snapshot_id: int, bindings: tuple[QuotaBinding, ...]
    ) -> None:
        for binding in bindings:
            binding_json = self._serialize(binding)
            await conn.execute(
                """
                INSERT INTO quota_binding_samples
                    (snapshot_id, model_id, reasoning_effort, confidence, binding_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    binding.model_id,
                    binding.reasoning_effort,
                    binding.confidence,
                    json.dumps(binding_json),
                ),
            )

    async def save_snapshot(self, snapshot: UsageSnapshot) -> int:
        self._check_coherence(snapshot)
        snapshot_json = self._serialize(snapshot)

        async with self._connection() as conn:
            try:
                await conn.execute("BEGIN")
                snapshot_id = await self._insert_snapshot_row(conn, snapshot, snapshot_json)
                await self._insert_pool_samples(conn, snapshot_id, snapshot.quota_pools)
                await self._insert_binding_samples(conn, snapshot_id, snapshot.quota_bindings)
                await conn.commit()
            except Exception as exc:
                await conn.rollback()
                raise SnapshotWriteError("failed to write snapshot") from exc

        return snapshot_id

    def _deserialize(self, snapshot_json: str) -> UsageSnapshot:
        try:
            raw = json.loads(snapshot_json)
            return UsageSnapshot.model_validate(raw)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise SnapshotReadError("stored snapshot is not a valid UsageSnapshot") from exc

    async def get_snapshot(self, snapshot_id: int) -> UsageSnapshot | None:
        async with self._connection() as conn:
            cursor = await conn.execute(
                "SELECT snapshot_json FROM snapshots WHERE id = ?", (snapshot_id,)
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return self._deserialize(row[0])

    async def get_latest_snapshot(self, provider: str | None = None) -> UsageSnapshot | None:
        results = await self.list_snapshots(provider=provider, limit=1)
        return results[0] if results else None

    async def list_snapshots(
        self,
        *,
        provider: str | None = None,
        limit: int = 100,
    ) -> tuple[UsageSnapshot, ...]:
        query = "SELECT snapshot_json FROM snapshots"
        params: list[Any] = []
        if provider is not None:
            query += " WHERE provider = ?"
            params.append(provider)
        query += " ORDER BY captured_at DESC, id DESC LIMIT ?"
        params.append(limit)

        async with self._connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()

        return tuple(self._deserialize(row[0]) for row in rows)
