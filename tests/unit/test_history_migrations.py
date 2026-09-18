"""Schema initialization/versioning tests. Fully offline (temp-file SQLite)."""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from quotapilot.history.errors import DatabaseInitializationError
from quotapilot.history.migrations import CURRENT_SCHEMA_VERSION, ensure_schema


async def test_fresh_database_initializes(tmp_path: Path) -> None:
    conn = await aiosqlite.connect(tmp_path / "fresh.db")
    try:
        await ensure_schema(conn)

        cursor = await conn.execute("SELECT version FROM schema_version")
        rows = await cursor.fetchall()
        assert rows == [(CURRENT_SCHEMA_VERSION,)]

        for table in ("snapshots", "quota_pool_samples", "quota_binding_samples"):
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            )
            assert await cursor.fetchone() is not None
    finally:
        await conn.close()


async def test_reopen_at_current_version_is_a_no_op(tmp_path: Path) -> None:
    db_path = tmp_path / "reopen.db"

    conn = await aiosqlite.connect(db_path)
    await ensure_schema(conn)
    await conn.close()

    conn = await aiosqlite.connect(db_path)
    try:
        await ensure_schema(conn)  # must not raise, must not duplicate anything
        cursor = await conn.execute("SELECT COUNT(*) FROM schema_version")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 1
    finally:
        await conn.close()


async def test_newer_schema_version_fails_clearly(tmp_path: Path) -> None:
    db_path = tmp_path / "newer.db"

    conn = await aiosqlite.connect(db_path)
    await ensure_schema(conn)
    await conn.execute("UPDATE schema_version SET version = ?", (CURRENT_SCHEMA_VERSION + 1,))
    await conn.commit()
    await conn.close()

    conn = await aiosqlite.connect(db_path)
    try:
        with pytest.raises(DatabaseInitializationError):
            await ensure_schema(conn)
    finally:
        await conn.close()


async def test_empty_version_table_in_existing_database_fails(tmp_path: Path) -> None:
    conn = await aiosqlite.connect(tmp_path / "empty-version.db")
    try:
        await ensure_schema(conn)
        await conn.execute("DELETE FROM schema_version")
        await conn.commit()

        with pytest.raises(DatabaseInitializationError, match="exactly one"):
            await ensure_schema(conn)

        # The failed validation rolled back its transaction; the connection
        # is still usable by diagnostics or orderly cleanup.
        cursor = await conn.execute("SELECT 1")
        assert await cursor.fetchone() == (1,)
    finally:
        await conn.close()


async def test_duplicate_version_rows_fail(tmp_path: Path) -> None:
    conn = await aiosqlite.connect(tmp_path / "duplicate-version.db")
    try:
        await ensure_schema(conn)
        await conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)", (CURRENT_SCHEMA_VERSION,)
        )
        await conn.commit()

        with pytest.raises(DatabaseInitializationError, match="exactly one"):
            await ensure_schema(conn)
    finally:
        await conn.close()


async def test_mixed_supported_and_unsupported_version_rows_fail(tmp_path: Path) -> None:
    conn = await aiosqlite.connect(tmp_path / "mixed-version.db")
    try:
        await ensure_schema(conn)
        await conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            (CURRENT_SCHEMA_VERSION + 1,),
        )
        await conn.commit()

        with pytest.raises(DatabaseInitializationError, match="exactly one"):
            await ensure_schema(conn)
    finally:
        await conn.close()


async def test_malformed_non_integer_version_fails(tmp_path: Path) -> None:
    conn = await aiosqlite.connect(tmp_path / "malformed-version.db")
    try:
        await ensure_schema(conn)
        await conn.execute("UPDATE schema_version SET version = 'not-an-integer'")
        await conn.commit()

        with pytest.raises(DatabaseInitializationError, match="integer"):
            await ensure_schema(conn)
    finally:
        await conn.close()


async def test_current_version_with_missing_required_table_fails(tmp_path: Path) -> None:
    conn = await aiosqlite.connect(tmp_path / "missing-table.db")
    try:
        await ensure_schema(conn)
        await conn.execute("DROP TABLE quota_binding_samples")
        await conn.commit()

        with pytest.raises(DatabaseInitializationError, match="missing required table"):
            await ensure_schema(conn)
    finally:
        await conn.close()


async def test_current_version_with_missing_required_column_fails(tmp_path: Path) -> None:
    conn = await aiosqlite.connect(tmp_path / "missing-column.db")
    try:
        await ensure_schema(conn)
        await conn.execute("ALTER TABLE snapshots DROP COLUMN plan_name")
        await conn.commit()

        with pytest.raises(DatabaseInitializationError, match="missing required column"):
            await ensure_schema(conn)
    finally:
        await conn.close()


async def test_nonempty_database_without_version_table_fails(tmp_path: Path) -> None:
    conn = await aiosqlite.connect(tmp_path / "unversioned.db")
    try:
        await conn.execute("CREATE TABLE unrelated (id INTEGER)")
        await conn.commit()

        with pytest.raises(DatabaseInitializationError, match="schema_version"):
            await ensure_schema(conn)
    finally:
        await conn.close()


async def test_older_schema_version_fails_clearly(tmp_path: Path) -> None:
    db_path = tmp_path / "older.db"

    conn = await aiosqlite.connect(db_path)
    await ensure_schema(conn)
    await conn.execute("UPDATE schema_version SET version = 0")
    await conn.commit()
    await conn.close()

    conn = await aiosqlite.connect(db_path)
    try:
        with pytest.raises(DatabaseInitializationError):
            await ensure_schema(conn)
    finally:
        await conn.close()


async def test_foreign_keys_pragma_is_enabled(tmp_path: Path) -> None:
    conn = await aiosqlite.connect(tmp_path / "fk.db")
    try:
        await ensure_schema(conn)
        cursor = await conn.execute("PRAGMA foreign_keys")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == 1
    finally:
        await conn.close()
