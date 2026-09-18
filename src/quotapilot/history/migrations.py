"""Database initialization and schema-version integrity checks.

Schema version 1 is the only version currently supported. A fresh, truly
empty database is initialized atomically; every existing database must have
exactly one integer version row and the complete version-1 table shape.
"""

from __future__ import annotations

from collections.abc import Collection

import aiosqlite

from .errors import DatabaseInitializationError

CURRENT_SCHEMA_VERSION = 1

_CREATE_TABLES_V1 = (
    """
    CREATE TABLE snapshots (
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
    )
    """,
    """
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
    )
    """,
    """
    CREATE INDEX idx_snapshots_provider_captured_at
        ON snapshots(provider, captured_at)
    """,
    """
    CREATE INDEX idx_quota_pool_samples_snapshot_id
        ON quota_pool_samples(snapshot_id)
    """,
    """
    CREATE INDEX idx_quota_binding_samples_snapshot_id
        ON quota_binding_samples(snapshot_id)
    """,
)

_REQUIRED_COLUMNS_V1: dict[str, frozenset[str]] = {
    "snapshots": frozenset(
        {
            "id",
            "provider",
            "account_key",
            "plan_name",
            "captured_at",
            "snapshot_json",
            "created_at",
        }
    ),
    "quota_pool_samples": frozenset(
        {
            "id",
            "snapshot_id",
            "pool_id",
            "provider",
            "kind",
            "scope",
            "used_fraction",
            "remaining_fraction",
            "starts_at",
            "resets_at",
            "window_seconds",
            "pool_json",
        }
    ),
    "quota_binding_samples": frozenset(
        {
            "id",
            "snapshot_id",
            "model_id",
            "reasoning_effort",
            "confidence",
            "binding_json",
        }
    ),
}


async def _user_tables(conn: aiosqlite.Connection) -> set[str]:
    cursor = await conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        """
    )
    return {str(row[0]) for row in await cursor.fetchall()}


async def _table_columns(conn: aiosqlite.Connection, table: str) -> set[str]:
    # `table` comes only from the fixed mapping above, never from user input.
    cursor = await conn.execute(f'PRAGMA table_info("{table}")')
    return {str(row[1]) for row in await cursor.fetchall()}


def _missing(required: Collection[str], actual: Collection[str]) -> list[str]:
    return sorted(set(required) - set(actual))


async def _validate_current_schema(conn: aiosqlite.Connection, tables: set[str]) -> None:
    missing_tables = _missing(_REQUIRED_COLUMNS_V1, tables)
    if missing_tables:
        raise DatabaseInitializationError(
            "database schema version 1 is missing required table(s): "
            + ", ".join(missing_tables)
        )

    for table, required_columns in _REQUIRED_COLUMNS_V1.items():
        missing_columns = _missing(required_columns, await _table_columns(conn, table))
        if missing_columns:
            raise DatabaseInitializationError(
                f"database schema version 1 table {table!r} is missing required column(s): "
                + ", ".join(missing_columns)
            )


async def _validate_version(conn: aiosqlite.Connection, tables: set[str]) -> None:
    if "schema_version" not in tables:
        raise DatabaseInitializationError(
            "existing database is missing the schema_version table"
        )

    cursor = await conn.execute("SELECT version FROM schema_version")
    rows = tuple(await cursor.fetchall())
    if len(rows) != 1:
        raise DatabaseInitializationError(
            "schema_version must contain exactly one version row"
        )

    version = rows[0][0]
    if type(version) is not int:
        raise DatabaseInitializationError("schema_version must contain one integer version")

    if version > CURRENT_SCHEMA_VERSION:
        raise DatabaseInitializationError(
            f"database schema version {version} is newer than this build supports "
            f"(supports up to {CURRENT_SCHEMA_VERSION}); refusing to open it"
        )
    if version < CURRENT_SCHEMA_VERSION:
        raise DatabaseInitializationError(
            f"database schema version {version} is older than current "
            f"({CURRENT_SCHEMA_VERSION}) and no migration path exists yet"
        )

    await _validate_current_schema(conn, tables)


async def ensure_schema(conn: aiosqlite.Connection) -> None:
    """Atomically initialize an empty database or validate an existing one.

    `PRAGMA foreign_keys` is connection-local, so it is enabled on every
    connection. `BEGIN IMMEDIATE` serializes the small initialization/check
    section and is sufficient for the current single-process design.
    """
    try:
        await conn.execute("PRAGMA foreign_keys = ON")
        cursor = await conn.execute("PRAGMA foreign_keys")
        foreign_keys = await cursor.fetchone()
        if foreign_keys is None or foreign_keys[0] != 1:
            raise DatabaseInitializationError("could not enable SQLite foreign keys")
        await conn.execute("BEGIN IMMEDIATE")

        tables = await _user_tables(conn)
        if not tables:
            await conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
            for statement in _CREATE_TABLES_V1:
                await conn.execute(statement)
            await conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (CURRENT_SCHEMA_VERSION,),
            )
        else:
            await _validate_version(conn, tables)

        await conn.commit()
    except DatabaseInitializationError:
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
        raise DatabaseInitializationError(
            "failed to initialize or validate database schema"
        ) from exc
