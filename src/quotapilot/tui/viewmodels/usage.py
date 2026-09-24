"""Bounded, privacy-safe quota pace projection for Usage and History."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from quotapilot.budget.engine import BudgetEngine
from quotapilot.budget.models import PoolBudgetAssessment
from quotapilot.history.repository import SnapshotRepository
from quotapilot.tui.state import ViewStatus


@dataclass(frozen=True, slots=True)
class UsageSample:
    captured_at: datetime
    pool: PoolBudgetAssessment
    stale: bool


@dataclass(frozen=True, slots=True)
class UsageState:
    status: ViewStatus = ViewStatus.INITIAL
    samples: tuple[UsageSample, ...] = ()
    message_id: str | None = None

    @property
    def latest(self) -> UsageSample | None:
        return self.samples[0] if self.samples else None

    @property
    def trend(self) -> tuple[float, ...]:
        latest = self.latest
        if latest is None or latest.pool.actual_usage is None:
            return ()
        comparable = [
            sample.pool.actual_usage
            for sample in reversed(self.samples)
            if sample.pool.pool_id == latest.pool.pool_id
            and sample.pool.actual_usage is not None
            and sample.pool.expected_usage is not None
        ]
        return tuple(comparable[-16:]) if len(comparable) >= 3 else ()


class UsageViewModel:
    def __init__(
        self,
        repository: SnapshotRepository,
        budget: BudgetEngine,
        provider: str | None,
    ) -> None:
        self._repository = repository
        self._budget = budget
        self._provider = provider
        self.state = UsageState()
        self.active = False

    async def load(
        self,
        publish: Callable[[UsageState], None],
        *,
        limit: int = 120,
    ) -> UsageState:
        if self.active:
            return self.state
        self.active = True
        self.state = UsageState(ViewStatus.LOADING, self.state.samples)
        publish(self.state)
        try:
            snapshots = await self._repository.list_snapshots(provider=self._provider, limit=limit)
            now = datetime.now(UTC)

            # BudgetEngine remains the only source of pace and state calculations.
            def project() -> tuple[UsageSample, ...]:
                rows: list[UsageSample] = []
                for index, snapshot in enumerate(snapshots):
                    report = self._budget.evaluate(
                        snapshot, now=now if index == 0 else snapshot.captured_at
                    )
                    pool = next(
                        (item for item in report.pools if item.pool_id == report.binding_pool_id),
                        report.pools[0] if report.pools else None,
                    )
                    if pool is not None:
                        rows.append(UsageSample(snapshot.captured_at, pool, report.is_stale))
                return tuple(rows)

            samples = await asyncio.to_thread(project)
            self.state = UsageState(
                ViewStatus.READY if samples else ViewStatus.EMPTY,
                samples,
                None if samples else "usage.no_snapshot",
            )
        except Exception:  # noqa: BLE001 - never display repository internals
            self.state = UsageState(ViewStatus.ERROR, self.state.samples, "usage.error")
        finally:
            self.active = False
        publish(self.state)
        return self.state
