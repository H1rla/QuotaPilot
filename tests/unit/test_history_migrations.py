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
