"""Capability/profile inspection view model."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from quotapilot.capabilities.enrichment import capability_views
from quotapilot.domain.usage import UsageSnapshot

from ..async_runner import AsyncRunner
from ..dependencies import GuiDependencies
from ..list_model import DictListModel
from ..mappers import map_models
from .base import BaseViewModel

_MODEL_ROLES = (
    "modelId",
    "provider",
    "routable",
    "routableText",
    "power",
    "cost",
    "latency",
    "effort",
    "profile",
    "source",
    "confidence",
    "verified",
    "freshness",
    "stale",
    "evidence",
    "warnings",
)

_EMPTY_MODEL = {
    "modelId": "Unknown",
    "source": "Unknown",
    "confidence": "Unknown",
    "verified": "Unknown",
    "effort": "Unknown",
    "freshness": "UNKNOWN",
    "evidence": [],
}


class ModelsViewModel(BaseViewModel):
    modelsChanged = Signal()

    def __init__(self, dependencies: GuiDependencies, runner: AsyncRunner) -> None:
        super().__init__()
        self._dependencies = dependencies
        self._runner = runner
        self.model = DictListModel(_MODEL_ROLES)
        self._selected: dict[str, Any] = dict(_EMPTY_MODEL)

    @Property(QObject, constant=True)
    def rows(self) -> QObject:
        return self.model

    @Property(dict, notify=modelsChanged)
    def selected(self) -> dict[str, Any]:
        return self._selected

    @Property(bool, notify=modelsChanged)
    def empty(self) -> bool:
        return self.model.rowCount() == 0

    @Slot()
    def load(self) -> None:
        if self.busy:
            return
        self._begin()

        async def operation() -> UsageSnapshot | None:
            return await self._dependencies.repository.get_latest_snapshot(
                provider=self._dependencies.effective.config.provider.default
            )

        def success(value: object) -> None:
            snapshot = value if isinstance(value, UsageSnapshot) else None
            if snapshot is None:
                rows: list[dict[str, Any]] = []
            else:
                enriched = self._dependencies.enricher.enrich(
                    snapshot.account.capabilities,
                    self._dependencies.registry,
                    evaluated_on=datetime.now(UTC).date(),
                )
                rows = map_models(capability_views(enriched))
            self.model.replace(rows)
            self._selected = rows[0] if rows else dict(_EMPTY_MODEL)
            self._finish()
            self.modelsChanged.emit()

        def failure(_error: Exception) -> None:
            self._fail("Model profiles are unavailable.", "Retry")

        self._runner.start(operation, success, failure)

    @Slot(int)
    def select(self, index: int) -> None:
        self._selected = self.model.get(index)
        self.modelsChanged.emit()
