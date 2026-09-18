"""Database initialization and schema-version handling.

Deliberately minimal (no migration framework): schema version 1 is the only
version that currently exists. `ensure_schema` fully creates it on a fresh
database, is a no-op on a database already at `CURRENT_SCHEMA_VERSION`, and
fails clearly (`DatabaseInitializationError`) on any other version — a
newer version this build predates, or an older one this build has no
migration path for yet. When schema version 2 is introduced, add its own
branch here rather than reaching for a framework.
"""

from __future__ import annotations

import aiosqlite

from .errors import DatabaseInitializationError

CURRENT_SCHEMA_VERSION = 1

_CREATE_TABLES_V1 = (
    """
    CREATE TABLE IF NOT EXISTS snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider TEXT NOT NULL,
        account_key TEXT,
        plan_name TEXT,
        captured_at TEXT NOT NULL,
        snapshot_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS quota_pool_samples (
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
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS quota_binding_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        snapshot_id INTEGER NOT NULL,
        model_id TEXT NOT NULL,
        reasoning_effort TEXT,
        confidence TEXT NOT NULL,
        binding_json TEXT NOT NULL,
        FOREIGN KEY(snapshot_id)
            REFERENCES snapshots(id)
            ON DELETE CASCADE
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_snapshots_provider_captured_at
        ON snapshots(provider, captured_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_quota_pool_samples_snapshot_id
        ON quota_pool_samples(snapshot_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_quota_binding_samples_snapshot_id
        ON quota_binding_samples(snapshot_id)
    """,
)


async def ensure_schema(conn: aiosqlite.Connection) -> None:
    """Initialize a fresh database or verify an existing one is compatible.

    `PRAGMA foreign_keys` is connection-local in SQLite (not persisted in
    the file), so this always re-enables it, on every connect, not just on
    first initialization.
    """
    await conn.execute("PRAGMA foreign_keys = ON")
    await conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")

    cursor = await conn.execute("SELECT version FROM schema_version LIMIT 1")
    row = await cursor.fetchone()

    if row is None:
        for statement in _CREATE_TABLES_V1:
            await conn.execute(statement)
        await conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)", (CURRENT_SCHEMA_VERSION,)
        )
        await conn.commit()
        return

    version = row[0]
    if version == CURRENT_SCHEMA_VERSION:
        return

    if version > CURRENT_SCHEMA_VERSION:
        raise DatabaseInitializationError(
            f"database schema version {version} is newer than this build supports "
            f"(supports up to {CURRENT_SCHEMA_VERSION}); refusing to open it"
        )

    raise DatabaseInitializationError(
        f"database schema version {version} is older than current "
        f"({CURRENT_SCHEMA_VERSION}) and no migration path exists yet"
    )
