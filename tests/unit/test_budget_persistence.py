"""Budget composition through the provider-independent persistence boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from quotapilot.budget.engine import BudgetEngine
from quotapilot.budget.models import BudgetConfig
from quotapilot.domain.account import AccountInfo
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.quota import QuotaPool
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.history.sqlite import SqliteSnapshotRepository
from quotapilot.services.budget import BudgetService


def _snapshot(now: datetime) -> UsageSnapshot:
    return UsageSnapshot(
        account=AccountInfo(
            provider="test-provider",
            account_id="raw-account-id-not-used-by-budget",
            capabilities=CapabilitySet(models=()),
            observed_at=now,
        ),
        quota_pools=(
            QuotaPool(
                id="weekly",
                provider="test-provider",
                kind="unknown",
                scope="unknown",
                used_fraction=0.55,
                remaining_fraction=0.45,
                starts_at=now - timedelta(days=3),
                resets_at=now + timedelta(days=4),
                window_seconds=7 * 86_400,
                metadata={"unknown": {"nested": "preserved"}},
            ),
        ),
        quota_bindings=(),
        captured_at=now,
    )


async def test_save_reload_budget_matches_direct_evaluation(tmp_path: Path) -> None:
    now = datetime(2026, 9, 18, 12, tzinfo=UTC)
    snapshot = _snapshot(now)
    repo = SqliteSnapshotRepository(tmp_path / "budget.db")
    snapshot_id = await repo.save_snapshot(snapshot)
    reloaded = await repo.get_snapshot(snapshot_id)
    assert reloaded is not None

    engine = BudgetEngine(BudgetConfig(timezone="UTC"))
    direct = engine.evaluate(snapshot, now=now)
    persisted = engine.evaluate(reloaded, now=now)

    assert persisted == direct


async def test_budget_service_loads_latest_snapshot(tmp_path: Path) -> None:
    now = datetime(2026, 9, 18, 12, tzinfo=UTC)
    repo = SqliteSnapshotRepository(tmp_path / "budget.db")
    await repo.save_snapshot(_snapshot(now))
    service = BudgetService(repo, BudgetEngine())

    report = await service.get_latest_report(now=now, provider="test-provider")

    assert report is not None
    assert report.binding_pool_id == "weekly"


async def test_budget_service_returns_none_when_no_snapshot_exists(tmp_path: Path) -> None:
    repo = SqliteSnapshotRepository(tmp_path / "empty.db")
    service = BudgetService(repo, BudgetEngine())

    assert (
        await service.get_latest_report(
            now=datetime(2026, 9, 18, 12, tzinfo=UTC),
            provider="unknown-provider",
        )
        is None
    )
