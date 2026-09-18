"""Deterministic offline product flow through dry-run planning."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from quotapilot.budget.engine import BudgetEngine
from quotapilot.capabilities.enrichment import CapabilityEnricher
from quotapilot.capabilities.loader import default_profile_directory
from quotapilot.capabilities.registry import ModelProfileRegistry
from quotapilot.config import load_effective_config
from quotapilot.domain.account import AccountInfo
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.model import AIModel
from quotapilot.domain.quota import QuotaPool
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.execution.models import ExecutionPlan, ExecutionResult
from quotapilot.execution.planner import ExecutionPlanner
from quotapilot.history.sqlite import SqliteSnapshotRepository
from quotapilot.routing.engine import RoutingEngine
from quotapilot.routing.profiler import TaskProfiler
from quotapilot.services.execution import ExecutionService
from quotapilot.services.routing import RoutingService

NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)


class NoExecutionAdapter:
    name = "offline-smoke"
    provider = "openai-codex"

    def command_preview(
        self,
        model_id: str,
        effort: str | None,
        working_directory: Path,
    ) -> tuple[str, ...]:
        return ("offline-smoke", model_id, effort or "default", str(working_directory))

    async def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        raise AssertionError(f"dry-run unexpectedly executed {plan.execution_id}")


class NoCaptureProvider:
    async def capture_usage(self) -> UsageSnapshot:
        raise AssertionError("fresh persisted dry-run unexpectedly captured live state")


def _snapshot() -> UsageSnapshot:
    return UsageSnapshot(
        account=AccountInfo(
            provider="openai-codex",
            capabilities=CapabilitySet(
                models=(
                    AIModel(
                        id="gpt-5.6-luna",
                        provider="openai-codex",
                        supported_efforts=("low", "medium", "high", "xhigh", "max"),
                    ),
                )
            ),
            observed_at=NOW,
        ),
        quota_pools=(
            QuotaPool(
                id="weekly",
                provider="openai-codex",
                kind="unknown",
                scope="unknown",
                used_fraction=0.3,
                remaining_fraction=0.7,
                starts_at=NOW - timedelta(days=1),
                resets_at=NOW + timedelta(days=6),
                window_seconds=7 * 86_400,
            ),
        ),
        quota_bindings=(),
        captured_at=NOW,
    )


@pytest.mark.asyncio
async def test_offline_config_snapshot_budget_enrich_route_and_dry_run(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "budget:\n  reserve_fraction: 0.1\nexecution:\n  mode: always_confirm\n",
        encoding="utf-8",
    )
    effective = load_effective_config(path=config_path, environ={})
    repository = SqliteSnapshotRepository(tmp_path / "smoke.db")
    await repository.save_snapshot(_snapshot())
    routing = RoutingService(
        repository,
        BudgetEngine(effective.config.budget),
        RoutingEngine(effective.config.routing),
        TaskProfiler(),
        CapabilityEnricher(),
        ModelProfileRegistry.from_directory(default_profile_directory()),
    )
    adapter = NoExecutionAdapter()
    execution = ExecutionService(
        NoCaptureProvider(),
        routing,
        adapter,
        ExecutionPlanner(effective.config.execution, id_factory=lambda: "offline-plan"),
        effective.config.execution,
        clock=lambda: NOW,
    )

    plan = await execution.create_plan(
        "Fix typo in README",
        working_directory=tmp_path,
        dry_run=True,
    )

    assert plan.dry_run is True
    assert plan.model_id == "gpt-5.6-luna"
    assert plan.adapter_name == "offline-smoke"
    assert "Fix typo in README" not in plan.model_dump_json()
