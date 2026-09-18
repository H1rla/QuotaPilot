"""Overview operational state backed by StatusService."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, Signal, Slot

from quotapilot.observability.models import StatusReport

from ..async_runner import AsyncRunner
from ..dependencies import GuiDependencies
from ..formatting import utc_now
from ..mappers import map_overview
from .base import BaseViewModel


class OverviewViewModel(BaseViewModel):
    overviewChanged = Signal()

    def __init__(self, dependencies: GuiDependencies, runner: AsyncRunner) -> None:
        super().__init__()
        self._dependencies = dependencies
        self._runner = runner
        self._data = map_overview(None)
        self._recommendation: dict[str, Any] = {}

    @Property(dict, notify=overviewChanged)
    def data(self) -> dict[str, Any]:
        return self._data

    @Property(dict, notify=overviewChanged)
    def recommendation(self) -> dict[str, Any]:
        return self._recommendation

    @Property(bool, notify=overviewChanged)
    def hasRecommendation(self) -> bool:  # noqa: N802
        return bool(self._recommendation)

    @Slot()
    def load(self) -> None:
        self._load(live=False)

    @Slot()
    def refresh(self) -> None:
        self._load(live=True)

    def _load(self, *, live: bool) -> None:
        if self.busy:
            return
        self._begin()

        async def operation() -> StatusReport | None:
            return await self._dependencies.status_service.get_status(
                now=utc_now(),
                provider=self._dependencies.effective.config.provider.default,
                refresh_provider=self._dependencies.provider if live else None,
            )

        def success(report: object) -> None:
            self._data = map_overview(
                report if isinstance(report, StatusReport) else None
            )
            self._finish()
            self.overviewChanged.emit()

        def failure(_error: Exception) -> None:
            self._fail(
                "Provider unavailable. Persisted state could not be loaded.",
                "Retry",
            )

        self._runner.start(operation, success, failure)

    def set_recommendation(self, recommendation: dict[str, Any]) -> None:
        self._recommendation = dict(recommendation)
        self.overviewChanged.emit()
