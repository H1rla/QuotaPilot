"""Orchestrate persisted snapshots, budgeting, profiling, and pure routing."""

from __future__ import annotations

from datetime import datetime

from quotapilot.budget.engine import BudgetEngine
from quotapilot.history.repository import SnapshotRepository
from quotapilot.routing.engine import RoutingEngine
from quotapilot.routing.models import RoutingRecommendation, TaskProfileOverrides
from quotapilot.routing.profiler import TaskProfiler


class RoutingService:
    """Build an advisory route from the latest coherent persisted snapshot."""

    def __init__(
        self,
        repository: SnapshotRepository,
        budget_engine: BudgetEngine,
        routing_engine: RoutingEngine,
        profiler: TaskProfiler,
    ) -> None:
        self._repository = repository
        self._budget_engine = budget_engine
        self._routing_engine = routing_engine
        self._profiler = profiler

    async def recommend_latest(
        self,
        summary: str,
        *,
        now: datetime,
        overrides: TaskProfileOverrides | None = None,
        provider: str | None = None,
    ) -> RoutingRecommendation | None:
        snapshot = await self._repository.get_latest_snapshot(provider=provider)
        if snapshot is None:
            return None
        budget = self._budget_engine.evaluate(snapshot, now=now)
        profile = self._profiler.profile(summary, overrides)
        return self._routing_engine.recommend(
            profile, budget, snapshot.account.capabilities
        )
