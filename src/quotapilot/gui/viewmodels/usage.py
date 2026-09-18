"""Historical actual-versus-expected quota state."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, Signal, Slot

from quotapilot.domain.usage import UsageSnapshot

from ..async_runner import AsyncRunner
from ..dependencies import GuiDependencies
from ..mappers import map_usage_point, map_usage_report
from .base import BaseViewModel


class UsageViewModel(BaseViewModel):
    usageChanged = Signal()

    def __init__(self, dependencies: GuiDependencies, runner: AsyncRunner) -> None:
        super().__init__()
        self._dependencies = dependencies
        self._runner = runner
        self._summary: list[dict[str, Any]] = []
        self._points: list[dict[str, Any]] = []

    @Property(list, notify=usageChanged)
    def summary(self) -> list[dict[str, Any]]:
        return self._summary

    @Property(list, notify=usageChanged)
    def points(self) -> list[dict[str, Any]]:
        return self._points

    @Property(bool, notify=usageChanged)
    def empty(self) -> bool:
        return not self._points

    @Slot()
    def load(self) -> None:
        if self.busy:
            return
        self._begin()

        async def operation() -> tuple[UsageSnapshot, ...]:
            return await self._dependencies.repository.list_snapshots(
                provider=self._dependencies.effective.config.provider.default,
                limit=120,
            )

        def success(value: object) -> None:
            snapshots = value if isinstance(value, tuple) else ()
            points: list[dict[str, Any]] = []
            latest_summary: list[dict[str, Any]] = []
            for snapshot in reversed(snapshots):
                report = self._dependencies.budget_engine.evaluate(
                    snapshot,
                    now=snapshot.captured_at,
                )
                pool = next(
                    (
                        item
                        for item in report.pools
                        if item.pool_id == report.binding_pool_id
                    ),
                    report.pools[0] if report.pools else None,
                )
                points.append(map_usage_point(snapshot.captured_at, pool))
                latest_summary = map_usage_report(report)
            self._points = points
            self._summary = latest_summary
            self._finish()
            self.usageChanged.emit()

        def failure(_error: Exception) -> None:
            self._fail("Usage history is unavailable.", "Retry")

        self._runner.start(operation, success, failure)
