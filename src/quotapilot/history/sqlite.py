"""SQLite-backed, provider-independent snapshot persistence.

Each save crosses one defensive serialization boundary. Privacy transforms,
the full snapshot JSON, child JSON, and relational query projections are all
derived from that same canonical copy before a transaction is opened.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite
import platformdirs
from pydantic import ValidationError

from quotapilot.domain.usage import UsageSnapshot

from .errors import (
    DatabaseInitializationError,
    PersistenceError,
    SnapshotCoherenceError,
    SnapshotReadError,
    SnapshotSerializationError,
    SnapshotWriteError,
)
from .migrations import ensure_schema

_APP_NAME = "quotapilot"
_PSEUDONYM_PREFIX = "sha256:"


@dataclass(frozen=True, slots=True)
class _CanonicalSnapshot:
    """All values written for one save, detached from caller-owned state."""

    snapshot: UsageSnapshot
    account_key: str | None
    snapshot_json: str
    pool_json: tuple[str, ...]
    binding_json: tuple[str, ...]


def default_database_path() -> Path:
    """Return the platform-safe default database path."""
    return Path(platformdirs.user_data_dir(_APP_NAME)) / f"{_APP_NAME}.db"


def _to_utc_isoformat(value: datetime) -> str:
    """Normalize timestamps so lexical ordering is chronological."""
    return value.astimezone(UTC).isoformat()


def _pseudonymous_account_key(provider: str, account_id: str | None) -> str | None:
    """Create a stable provider-scoped local correlation key.

    This is a one-way digest, not a secret or authentication credential. The
    prefix identifies the local correlation value as a digest, not a secret.
    """
    if account_id is None:
        return None
    digest = hashlib.sha256(f"{provider}\0{account_id}".encode()).hexdigest()
    return f"{_PSEUDONYM_PREFIX}{digest}"


def _replace_exact_string(value: Any, target: str, replacement: str) -> Any:
    """Remove duplicate appearances of a raw account id from the copy."""
    if isinstance(value, dict):
        return {
            key: _replace_exact_string(item, target, replacement)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_replace_exact_string(item, target, replacement) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_exact_string(item, target, replacement) for item in value)
    if isinstance(value, str) and value == target:
        return replacement
    return value


def _encode_json(value: Any, description: str) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise SnapshotSerializationError(f"failed to encode {description}") from exc


class SqliteSnapshotRepository:
    """Local SQLite implementation of the provider-neutral repository."""

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
                "failed to create the database directory"
            ) from exc

        try:
            conn = await aiosqlite.connect(self._database_path)
        except Exception as exc:
            raise DatabaseInitializationError("failed to open the snapshot database") from exc

        try:
            await ensure_schema(conn)
        except PersistenceError:
            try:
                await conn.close()
            except Exception:  # noqa: BLE001
                pass
            raise
        except Exception as exc:
            try:
                await conn.close()
            except Exception:  # noqa: BLE001
                pass
            raise DatabaseInitializationError(
                "failed to initialize the snapshot database"
            ) from exc

        try:
            yield conn
        finally:
            # A per-call connection is discarded even if close itself reports
            # an error; public operation errors retain their typed taxonomy.
            try:
                await conn.close()
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _check_coherence(snapshot: UsageSnapshot) -> None:
        """Reject cross-provider, duplicate, or dangling snapshot identity."""
        if snapshot.captured_at.utcoffset() is None:
            raise SnapshotCoherenceError("captured_at must be timezone-aware")

        provider = snapshot.account.provider
        pool_ids = [pool.id for pool in snapshot.quota_pools]
        if len(pool_ids) != len(set(pool_ids)):
            raise SnapshotCoherenceError("quota pool ids must be unique within a snapshot")

        if any(pool.provider != provider for pool in snapshot.quota_pools):
            raise SnapshotCoherenceError(
                "all quota pool providers must match snapshot.account.provider"
            )

        if any(model.provider != provider for model in snapshot.account.capabilities.models):
            raise SnapshotCoherenceError(
                "all model providers must match snapshot.account.provider"
            )

        known_pool_ids = set(pool_ids)
        for binding in snapshot.quota_bindings:
            if len(binding.quota_pool_ids) != len(set(binding.quota_pool_ids)):
                raise SnapshotCoherenceError(
                    "a binding must not reference the same quota pool more than once"
                )
            if any(pool_id not in known_pool_ids for pool_id in binding.quota_pool_ids):
                raise SnapshotCoherenceError(
                    "a binding references a quota pool not present in this snapshot"
                )

    @classmethod
    def _canonicalize(cls, snapshot: UsageSnapshot) -> _CanonicalSnapshot:
        """Serialize once, pseudonymize identity, validate, and prebuild rows."""
        try:
            raw = snapshot.model_dump(mode="json", round_trip=True)
        except Exception as exc:  # noqa: BLE001
            raise SnapshotSerializationError("failed to serialize UsageSnapshot") from exc

        account = raw.get("account")
        if not isinstance(account, dict):
            raise SnapshotSerializationError("serialized snapshot has no account object")
        provider = account.get("provider")
        account_id = account.get("account_id")
        if not isinstance(provider, str) or not (
            account_id is None or isinstance(account_id, str)
        ):
            raise SnapshotSerializationError("serialized snapshot has invalid account identity")

        account_key = _pseudonymous_account_key(provider, account_id)
        if account_id is not None and account_key is not None:
            raw = _replace_exact_string(raw, account_id, account_key)

        try:
            canonical_snapshot = UsageSnapshot.model_validate(raw)
        except ValidationError as exc:
            raise SnapshotSerializationError(
                "persistence-safe snapshot failed domain validation"
            ) from exc
        cls._check_coherence(canonical_snapshot)

        raw_pools = raw.get("quota_pools")
        raw_bindings = raw.get("quota_bindings")
        if not isinstance(raw_pools, list) or not isinstance(raw_bindings, list):
            raise SnapshotSerializationError("serialized snapshot collections are invalid")

        return _CanonicalSnapshot(
            snapshot=canonical_snapshot,
            account_key=account_key,
            snapshot_json=_encode_json(raw, "UsageSnapshot"),
            pool_json=tuple(_encode_json(pool, "QuotaPool") for pool in raw_pools),
            binding_json=tuple(
                _encode_json(binding, "QuotaBinding") for binding in raw_bindings
            ),
        )

    async def _insert_snapshot_row(
        self, conn: aiosqlite.Connection, canonical: _CanonicalSnapshot
    ) -> int:
        snapshot = canonical.snapshot
        cursor = await conn.execute(
            """
            INSERT INTO snapshots
                (provider, account_key, plan_name, captured_at, snapshot_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.account.provider,
                canonical.account_key,
                snapshot.account.plan_name,
                _to_utc_isoformat(snapshot.captured_at),
                canonical.snapshot_json,
                _to_utc_isoformat(datetime.now(UTC)),
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("snapshot insert returned no row id")
        return cursor.lastrowid

    async def _insert_pool_samples(
        self, conn: aiosqlite.Connection, snapshot_id: int, canonical: _CanonicalSnapshot
    ) -> None:
        for pool, pool_json in zip(
            canonical.snapshot.quota_pools, canonical.pool_json, strict=True
        ):
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
                    pool_json,
                ),
            )

    async def _insert_binding_samples(
        self, conn: aiosqlite.Connection, snapshot_id: int, canonical: _CanonicalSnapshot
    ) -> None:
        for binding, binding_json in zip(
            canonical.snapshot.quota_bindings, canonical.binding_json, strict=True
        ):
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
                    binding_json,
                ),
            )

    async def save_snapshot(self, snapshot: UsageSnapshot) -> int:
        self._check_coherence(snapshot)
        canonical = self._canonicalize(snapshot)

        async with self._connection() as conn:
            try:
                await conn.execute("BEGIN")
                snapshot_id = await self._insert_snapshot_row(conn, canonical)
                await self._insert_pool_samples(conn, snapshot_id, canonical)
                await self._insert_binding_samples(conn, snapshot_id, canonical)
                await conn.commit()
            except PersistenceError:
                try:
                    await conn.rollback()
                except Exception:  # noqa: BLE001
                    pass
                raise
            except Exception as exc:
                try:
                    await conn.rollback()
                except Exception:  # noqa: BLE001
                    pass
                raise SnapshotWriteError("failed to write snapshot") from exc

        return snapshot_id

    @staticmethod
    def _deserialize(snapshot_json: object) -> UsageSnapshot:
        try:
            raw = json.loads(snapshot_json)  # type: ignore[arg-type]
            return UsageSnapshot.model_validate(raw)
        except (TypeError, ValueError) as exc:
            raise SnapshotReadError("stored snapshot is not a valid UsageSnapshot") from exc

    async def get_snapshot(self, snapshot_id: int) -> UsageSnapshot | None:
        try:
            async with self._connection() as conn:
                cursor = await conn.execute(
                    "SELECT snapshot_json FROM snapshots WHERE id = ?", (snapshot_id,)
                )
                row = await cursor.fetchone()
            if row is None:
                return None
            return self._deserialize(row[0])
        except PersistenceError:
            raise
        except Exception as exc:
            raise SnapshotReadError("failed to read snapshot") from exc

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

        try:
            async with self._connection() as conn:
                cursor = await conn.execute(query, params)
                rows = await cursor.fetchall()
            return tuple(self._deserialize(row[0]) for row in rows)
        except PersistenceError:
            raise
        except Exception as exc:
            raise SnapshotReadError("failed to list snapshots") from exc
