"""Tests for `SqliteSnapshotRepository`. Fully offline (temp-file SQLite;
richer snapshots come from `OpenAICodexProvider` against a fake stdio peer,
never the real `codex` binary or network).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from _fake_openai_codex import fake_provider

from quotapilot.domain.account import AccountInfo
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.model import AIModel
from quotapilot.domain.quota import QuotaBinding, QuotaPool
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.history.errors import SnapshotCoherenceError, SnapshotWriteError
from quotapilot.history.sqlite import SqliteSnapshotRepository


def _account(now: datetime, *, account_id: str | None = "acct_x") -> AccountInfo:
    return AccountInfo(
        provider="openai-codex",
        account_id=account_id,
        plan_name="pro",
        capabilities=CapabilitySet(
            models=(AIModel(id="m1", provider="openai-codex"),),
            metadata={"account_type": "chatgpt"},
        ),
        observed_at=now,
    )


def _snapshot(
    now: datetime,
    *,
    pools: tuple[QuotaPool, ...] = (),
    bindings: tuple[QuotaBinding, ...] = (),
    metadata: dict | None = None,
) -> UsageSnapshot:
    return UsageSnapshot(
        account=_account(now),
        quota_pools=pools,
        quota_bindings=bindings,
        captured_at=now,
        metadata=metadata or {},
    )


# --- round trip / semantic equality ------------------------------------------------


async def test_save_and_load_round_trip_is_semantically_equal(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    now = datetime.now(UTC)
    pool = QuotaPool(
        id="p1:primary",
        provider="openai-codex",
        kind="unknown",
        scope="model",
        used_fraction=0.42,
        remaining_fraction=0.58,
        starts_at=now - timedelta(hours=1),
        resets_at=now + timedelta(hours=4),
        window_seconds=3600 * 5,
        applies_to_models=("m1",),
        raw_name="Some Pool",
        metadata={"provenance": {"scope": {"basis": "provider"}}},
    )
    binding = QuotaBinding(
        model_id="m1",
        reasoning_effort="high",
        quota_pool_ids=("p1:primary",),
        confidence="observed",
        metadata={"provenance": {"basis": "inferred"}},
    )
    snapshot = _snapshot(now, pools=(pool,), bindings=(binding,), metadata={"k": "v"})

    snapshot_id = await repo.save_snapshot(snapshot)
    loaded = await repo.get_snapshot(snapshot_id)

    assert loaded == snapshot


async def test_zero_pools_and_bindings_round_trip(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    now = datetime.now(UTC)
    snapshot = _snapshot(now)

    snapshot_id = await repo.save_snapshot(snapshot)
    loaded = await repo.get_snapshot(snapshot_id)

    assert loaded is not None
    assert loaded.quota_pools == ()
    assert loaded.quota_bindings == ()


async def test_multiple_pools_and_bindings_all_survive(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    now = datetime.now(UTC)
    pools = tuple(
        QuotaPool(id=f"p{i}:primary", provider="openai-codex", kind="unknown", scope="unknown")
        for i in range(4)
    )
    bindings = tuple(
        QuotaBinding(model_id=f"m{i}", quota_pool_ids=(f"p{i}:primary",), confidence="observed")
        for i in range(4)
    )
    snapshot = _snapshot(now, pools=pools, bindings=bindings)

    snapshot_id = await repo.save_snapshot(snapshot)
    loaded = await repo.get_snapshot(snapshot_id)

    assert loaded is not None
    assert {p.id for p in loaded.quota_pools} == {f"p{i}:primary" for i in range(4)}
    assert {b.model_id for b in loaded.quota_bindings} == {f"m{i}" for i in range(4)}


async def test_unknown_kind_and_scope_round_trip(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    now = datetime.now(UTC)
    pool = QuotaPool(
        id="p1:unrepresented", provider="openai-codex", kind="unknown", scope="unknown"
    )
    snapshot = _snapshot(now, pools=(pool,))

    snapshot_id = await repo.save_snapshot(snapshot)
    loaded = await repo.get_snapshot(snapshot_id)

    assert loaded is not None
    assert loaded.quota_pools[0].kind == "unknown"
    assert loaded.quota_pools[0].scope == "unknown"


async def test_reasoning_effort_and_confidence_round_trip(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    now = datetime.now(UTC)
    pool = QuotaPool(id="p1:primary", provider="openai-codex", kind="unknown", scope="model")
    binding = QuotaBinding(
        model_id="m1",
        reasoning_effort="xhigh",
        quota_pool_ids=("p1:primary",),
        confidence="observed",
    )
    snapshot = _snapshot(now, pools=(pool,), bindings=(binding,))

    snapshot_id = await repo.save_snapshot(snapshot)
    loaded = await repo.get_snapshot(snapshot_id)

    assert loaded is not None
    assert loaded.quota_bindings[0].reasoning_effort == "xhigh"
    assert loaded.quota_bindings[0].confidence == "observed"


async def test_datetimes_round_trip_timezone_aware(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    # A non-UTC offset, to prove normalization-for-storage doesn't lose the instant.
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst).replace(microsecond=123456)
    snapshot = _snapshot(now)

    snapshot_id = await repo.save_snapshot(snapshot)
    loaded = await repo.get_snapshot(snapshot_id)

    assert loaded is not None
    assert loaded.captured_at == now
    assert loaded.captured_at.tzinfo is not None


# --- metadata / provenance / unknown-data preservation -----------------------------


async def test_real_capture_metadata_provenance_and_raw_observation_survive(
    tmp_path: Path,
) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    provider = fake_provider()
    snapshot = await provider.capture_usage()

    snapshot_id = await repo.save_snapshot(snapshot)
    loaded = await repo.get_snapshot(snapshot_id)

    assert loaded is not None
    assert loaded == snapshot
    # raw_observation (unknown top-level provider fields, redacted)
    assert (
        loaded.metadata["raw_observation"]["rate_limits_read"]["accountId"] == "REDACTED"
    )
    # provenance on pools/bindings
    for pool in loaded.quota_pools:
        assert "provenance" in pool.metadata
    for binding in loaded.quota_bindings:
        assert "provenance" in binding.metadata
    # capability metadata (unknown/derived account info)
    assert "account_type" in loaded.account.capabilities.metadata


async def test_unknown_nested_metadata_survives(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    now = datetime.now(UTC)
    pool = QuotaPool(
        id="p1:primary",
        provider="openai-codex",
        kind="unknown",
        scope="unknown",
        metadata={
            "raw_snapshot": {
                "futureField": "future-value",
                "nested": {"deeper": [1, 2, {"three": 3}]},
            }
        },
    )
    snapshot = _snapshot(now, pools=(pool,))

    snapshot_id = await repo.save_snapshot(snapshot)
    loaded = await repo.get_snapshot(snapshot_id)

    assert loaded is not None
    raw = loaded.quota_pools[0].metadata["raw_snapshot"]
    assert raw["futureField"] == "future-value"
    assert raw["nested"]["deeper"] == [1, 2, {"three": 3}]


# --- coherence / transaction --------------------------------------------------------


async def test_dangling_binding_reference_is_rejected_before_write(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    now = datetime.now(UTC)
    pool = QuotaPool(id="p1:primary", provider="openai-codex", kind="unknown", scope="unknown")
    dangling = QuotaBinding(
        model_id="m1", quota_pool_ids=("does-not-exist",), confidence="observed"
    )
    snapshot = _snapshot(now, pools=(pool,), bindings=(dangling,))

    with pytest.raises(SnapshotCoherenceError):
        await repo.save_snapshot(snapshot)

    assert await repo.list_snapshots() == ()


async def test_inconsistent_pool_provider_is_rejected(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    now = datetime.now(UTC)
    mismatched_pool = QuotaPool(
        id="p1:primary", provider="some-other-provider", kind="unknown", scope="unknown"
    )
    snapshot = _snapshot(now, pools=(mismatched_pool,))

    with pytest.raises(SnapshotCoherenceError):
        await repo.save_snapshot(snapshot)


async def test_child_write_failure_leaves_no_partial_snapshot(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    now = datetime.now(UTC)
    pool = QuotaPool(id="p1:primary", provider="openai-codex", kind="unknown", scope="unknown")
    binding = QuotaBinding(model_id="m1", quota_pool_ids=("p1:primary",), confidence="observed")
    snapshot = _snapshot(now, pools=(pool,), bindings=(binding,))

    async def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated child-write failure")

    repo._insert_binding_samples = boom  # type: ignore[method-assign]

    with pytest.raises(SnapshotWriteError):
        await repo.save_snapshot(snapshot)

    assert await repo.list_snapshots() == ()


# --- history: latest / list / provider filter / ordering ---------------------------


async def test_get_latest_snapshot_returns_most_recent(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    t1 = datetime.now(UTC) - timedelta(hours=2)
    t2 = datetime.now(UTC) - timedelta(hours=1)
    t3 = datetime.now(UTC)

    await repo.save_snapshot(_snapshot(t1))
    await repo.save_snapshot(_snapshot(t3))
    await repo.save_snapshot(_snapshot(t2))  # inserted last, but not chronologically latest

    latest = await repo.get_latest_snapshot()

    assert latest is not None
    assert latest.captured_at == t3


async def test_list_snapshots_orders_newest_first_and_respects_limit(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    base = datetime.now(UTC)
    times = [base - timedelta(minutes=i) for i in range(5)]
    for t in reversed(times):
        await repo.save_snapshot(_snapshot(t))

    listed = await repo.list_snapshots(limit=3)

    assert [s.captured_at for s in listed] == times[:3]


async def test_provider_filter_only_returns_matching_provider(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    now = datetime.now(UTC)

    other_account = AccountInfo(
        provider="some-other-provider",
        capabilities=CapabilitySet(models=()),
        observed_at=now,
    )
    other_snapshot = UsageSnapshot(
        account=other_account, quota_pools=(), quota_bindings=(), captured_at=now
    )
    await repo.save_snapshot(other_snapshot)
    await repo.save_snapshot(_snapshot(now + timedelta(seconds=1)))

    filtered = await repo.list_snapshots(provider="openai-codex")
    latest_filtered = await repo.get_latest_snapshot(provider="openai-codex")

    assert len(filtered) == 1
    assert filtered[0].account.provider == "openai-codex"
    assert latest_filtered is not None
    assert latest_filtered.account.provider == "openai-codex"


async def test_identical_state_captured_twice_is_not_deduplicated(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    t1 = datetime.now(UTC) - timedelta(minutes=1)
    t2 = datetime.now(UTC)
    pool = QuotaPool(
        id="p1:primary", provider="openai-codex", kind="unknown", scope="unknown",
        used_fraction=0.5, remaining_fraction=0.5,
    )

    id1 = await repo.save_snapshot(_snapshot(t1, pools=(pool,)))
    id2 = await repo.save_snapshot(_snapshot(t2, pools=(pool,)))

    assert id1 != id2
    listed = await repo.list_snapshots()
    assert len(listed) == 2


async def test_get_snapshot_returns_none_for_unknown_id(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    assert await repo.get_snapshot(999999) is None


async def test_get_latest_snapshot_returns_none_when_empty(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "db.sqlite")
    assert await repo.get_latest_snapshot() is None


# --- reopen / cross-instance -----------------------------------------------------


async def test_reopening_database_with_new_repository_instance_sees_prior_data(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "db.sqlite"
    now = datetime.now(UTC)

    first = SqliteSnapshotRepository(db_path)
    snapshot_id = await first.save_snapshot(_snapshot(now))

    second = SqliteSnapshotRepository(db_path)
    loaded = await second.get_snapshot(snapshot_id)

    assert loaded is not None
    assert loaded.captured_at == now


async def test_default_database_path_uses_platformdirs_not_hardcoded_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from quotapilot.history import sqlite as sqlite_module

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    path = sqlite_module.default_database_path()

    assert str(tmp_path) in str(path)
    assert path.name == "quotapilot.db"
