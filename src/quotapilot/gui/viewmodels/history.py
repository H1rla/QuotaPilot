"""Privacy-safe snapshot history; Phase 6 intentionally has no execution audit."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from quotapilot.domain.usage import UsageSnapshot

from ..async_runner import AsyncRunner
from ..dependencies import GuiDependencies
from ..list_model import DictListModel
from ..mappers import map_usage_point
from .base import BaseViewModel


class HistoryViewModel(BaseViewModel):
    historyChanged = Signal()

    def __init__(self, dependencies: GuiDependencies, runner: AsyncRunner) -> None:
        super().__init__()
        self._dependencies = dependencies
        self._runner = runner
        self.model = DictListModel(
            (
                "capturedAt",
                "capturedText",
                "actual",
                "actualText",
                "expected",
                "expectedText",
                "delta",
                "statusValue",
            )
        )
        self._items: list[dict[str, Any]] = []

    @Property(QObject, constant=True)
    def rows(self) -> QObject:
        return self.model

    @Property(list, notify=historyChanged)
    def items(self) -> list[dict[str, Any]]:
        return self._items

    @Property(bool, notify=historyChanged)
    def empty(self) -> bool:
        return not self._items

    @Slot()
    def load(self) -> None:
        if self.busy:
            return
        self._begin()

        async def operation() -> tuple[UsageSnapshot, ...]:
            return await self._dependencies.repository.list_snapshots(
                provider=self._dependencies.effective.config.provider.default,
                limit=200,
            )

        def success(value: object) -> None:
            snapshots = value if isinstance(value, tuple) else ()
            rows: list[dict[str, Any]] = []
            for snapshot in snapshots:
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
                rows.append(map_usage_point(snapshot.captured_at, pool))
            self.model.replace(rows)
            self._items = rows
            self._finish()
            self.historyChanged.emit()

        def failure(_error: Exception) -> None:
            self._fail("Snapshot history is unavailable.", "Retry")
            self.historyChanged.emit()

        self._runner.start(operation, success, failure)
