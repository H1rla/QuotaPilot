"""Provider-independent persistence -> budget -> routing integration test."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from quotapilot.budget.engine import BudgetEngine
from quotapilot.domain.account import AccountInfo
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.model import AIModel
from quotapilot.domain.quota import QuotaPool
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.history.sqlite import SqliteSnapshotRepository
from quotapilot.routing.engine import RoutingEngine
from quotapilot.routing.profiler import TaskProfiler


async def test_persist_reload_budget_route_matches_direct_evaluation(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 9, 18, 12, tzinfo=UTC)
    models = (
        AIModel(
            id="efficient",
            provider="test-provider",
            selectable=True,
            supported_efforts=("normal", "deep"),
            effort_order=("normal", "deep"),
            relative_power=0.55,
            relative_cost=0.25,
            relative_latency=0.20,
        ),
        AIModel(
            id="capable",
            provider="test-provider",
            selectable=True,
            supported_efforts=("normal", "deep"),
            effort_order=("normal", "deep"),
            relative_power=0.90,
            relative_cost=0.80,
            relative_latency=0.65,
        ),
    )
    snapshot = UsageSnapshot(
        account=AccountInfo(
            provider="test-provider",
            account_id="private-account-id",
            capabilities=CapabilitySet(
                models=models,
                supports_reasoning_effort=True,
                supports_model_selection=True,
            ),
            observed_at=now,
        ),
        quota_pools=(
            QuotaPool(
                id="weekly",
                provider="test-provider",
                kind="unknown",
                scope="unknown",
                used_fraction=0.5,
                remaining_fraction=0.5,
                starts_at=now - timedelta(days=3),
                resets_at=now + timedelta(days=4),
                window_seconds=7 * 86_400,
            ),
        ),
        quota_bindings=(),
        captured_at=now,
    )
    repository = SqliteSnapshotRepository(tmp_path / "snapshots.sqlite")
    snapshot_id = await repository.save_snapshot(snapshot)
    loaded = await repository.get_snapshot(snapshot_id)
    assert loaded is not None

    profile = TaskProfiler().profile("Implement a local parser helper")
    direct_budget = BudgetEngine().evaluate(snapshot, now=now)
    loaded_budget = BudgetEngine().evaluate(loaded, now=now)
    engine = RoutingEngine()

    direct = engine.recommend(profile, direct_budget, snapshot.account.capabilities)
    reloaded = engine.recommend(profile, loaded_budget, loaded.account.capabilities)

    assert reloaded == direct
    assert reloaded.task_profile.summary == "Implement a local parser helper"
