"""Compose persisted snapshots with the pure Budget Engine."""

from __future__ import annotations

from datetime import datetime

from quotapilot.budget.engine import BudgetEngine
from quotapilot.budget.models import BudgetReport
from quotapilot.history.repository import SnapshotRepository


class BudgetService:
    """Load one coherent persisted snapshot and evaluate it without refreshing."""

    def __init__(self, repository: SnapshotRepository, engine: BudgetEngine) -> None:
        self._repository = repository
        self._engine = engine

    async def get_latest_report(
        self,
        *,
        now: datetime,
        provider: str | None = None,
    ) -> BudgetReport | None:
        snapshot = await self._repository.get_latest_snapshot(provider=provider)
        if snapshot is None:
            return None
        return self._engine.evaluate(snapshot, now=now)
