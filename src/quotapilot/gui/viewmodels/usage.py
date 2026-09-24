"""Persisted quota summary and shared daily forecast for QML."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from PySide6.QtCore import Property, Signal, Slot

from quotapilot.budget.forecast import DailyForecastService
from quotapilot.domain.usage import UsageSnapshot

from ..async_runner import AsyncRunner
from ..dependencies import GuiDependencies
from ..mappers import map_daily_forecast, map_usage_report
from .base import BaseViewModel


class UsageViewModel(BaseViewModel):
    usageChanged = Signal()

    def __init__(
        self, dependencies: GuiDependencies, runner: AsyncRunner,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        super().__init__()
        self._dependencies = dependencies
        self._runner = runner
        self._clock = clock or (lambda: datetime.now(UTC))
        self._summary: list[dict[str, Any]] = []
        self._points: list[dict[str, Any]] = []
        self._forecast_reason = "no_snapshots"
        self._forecast_stale = False

    @Property(list, notify=usageChanged)
    def summary(self) -> list[dict[str, Any]]:
        return self._summary

    @Property(list, notify=usageChanged)
    def points(self) -> list[dict[str, Any]]:
        return self._points

    @Property(bool, notify=usageChanged)
    def empty(self) -> bool:
        return not self._summary

    @Property(str, notify=usageChanged)
    def forecastReason(self) -> str:  # noqa: N802 - QML property
        return self._forecast_reason

    @Property(bool, notify=usageChanged)
    def forecastStale(self) -> bool:  # noqa: N802 - QML property
        return self._forecast_stale

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
            now = self._clock()
            forecast = DailyForecastService(self._dependencies.budget_engine).calculate(
                snapshots, now=now
            )
            latest_summary: list[dict[str, Any]] = []
            if snapshots:
                snapshot = max(snapshots, key=lambda item: item.captured_at)
                report = self._dependencies.budget_engine.evaluate(
                    snapshot,
                    now=now,
                )
                latest_summary = map_usage_report(report)
            self._points = map_daily_forecast(forecast)
            self._forecast_reason = (
                forecast.unavailable_reason.value if forecast.unavailable_reason else ""
            )
            self._forecast_stale = forecast.stale
            self._summary = latest_summary
            self._finish()
            self.usageChanged.emit()

        def failure(_error: Exception) -> None:
            self._fail("Usage history is unavailable.", "Retry")

        self._runner.start(operation, success, failure)
