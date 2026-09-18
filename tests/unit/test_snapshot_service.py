"""`SnapshotService` glue test: provider.capture_usage() -> repository.save_snapshot()."""

from __future__ import annotations

from pathlib import Path

from _fake_openai_codex import fake_provider

from quotapilot.history.sqlite import SqliteSnapshotRepository
from quotapilot.services.snapshot import SnapshotService, StoredSnapshot


async def test_capture_and_store_persists_a_coherent_snapshot(tmp_path: Path) -> None:
    provider = fake_provider()
    repository = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    service = SnapshotService(provider, repository)

    result = await service.capture_and_store()

    assert isinstance(result, StoredSnapshot)
    assert result.id > 0

    reloaded = await repository.get_snapshot(result.id)
    assert reloaded == result.snapshot
