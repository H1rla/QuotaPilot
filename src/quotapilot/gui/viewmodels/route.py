"""Task profiling and advisory routing without execution side effects."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, Signal, Slot

from quotapilot.routing.models import (
    RoutingRecommendation,
    TaskClass,
    TaskProfileOverrides,
)

from ..async_runner import AsyncRunner
from ..dependencies import GuiDependencies
from ..formatting import utc_now
from ..mappers import map_route
from .base import BaseViewModel

_EMPTY_ROUTE: dict[str, Any] = {
    "model": "Unavailable",
    "effort": "Unavailable",
    "taskClass": "unknown",
    "confidence": "unknown",
    "pressureText": "Unknown",
    "profile": {
        "complexity": 0.0,
        "ambiguity": 0.0,
        "failureCost": 0.0,
        "verifiability": 0.0,
    },
    "explanation": [],
    "escalation": [],
}


class RouteViewModel(BaseViewModel):
    routeChanged = Signal()
    recommendationReady = Signal(object)

    def __init__(self, dependencies: GuiDependencies, runner: AsyncRunner) -> None:
        super().__init__()
        self._dependencies = dependencies
        self._runner = runner
        self._task = ""
        self._result: dict[str, Any] = dict(_EMPTY_ROUTE)
        self._has_result = False

    @Property(str, notify=routeChanged)
    def task(self) -> str:
        return self._task

    @Property(dict, notify=routeChanged)
    def result(self) -> dict[str, Any]:
        return self._result

    @Property(bool, notify=routeChanged)
    def hasResult(self) -> bool:  # noqa: N802
        return self._has_result

    @Slot(str)
    def analyze(self, task: str) -> None:
        self._analyze(task, None)

    @Slot(str, str, float, float, float, float, float, float)
    def analyzeWithOverrides(  # noqa: N802
        self,
        task: str,
        task_class: str,
        complexity: float,
        ambiguity: float,
        failure_cost: float,
        verifiability: float,
        context_demand: float,
        latency_sensitivity: float,
    ) -> None:
        overrides = TaskProfileOverrides(
            task_class=TaskClass(task_class),
            complexity=complexity,
            ambiguity=ambiguity,
            failure_cost=failure_cost,
            verifiability=verifiability,
            context_demand=context_demand,
            latency_sensitivity=latency_sensitivity,
        )
        self._analyze(task, overrides)

    def _analyze(self, task: str, overrides: TaskProfileOverrides | None) -> None:
        if self.busy:
            return
        self._task = task.strip()
        if not self._task:
            self._fail("Enter a task before analysis.", "Focus task input")
            return
        self._begin()
        self.routeChanged.emit()

        async def operation() -> RoutingRecommendation | None:
            return await self._dependencies.routing_service.recommend_latest(
                self._task,
                now=utc_now(),
                overrides=overrides,
                provider=self._dependencies.effective.config.provider.default,
            )

        def success(value: object) -> None:
            recommendation = value if isinstance(value, RoutingRecommendation) else None
            if recommendation is None:
                self._result = dict(_EMPTY_ROUTE)
                self._has_result = False
                self._fail("No persisted snapshot. Refresh quota before routing.", "Refresh")
                self.routeChanged.emit()
                return
            self._result = map_route(recommendation)
            self._has_result = True
            self._finish()
            self.routeChanged.emit()
            self.recommendationReady.emit(self._result)

        def failure(_error: Exception) -> None:
            self._result = dict(_EMPTY_ROUTE)
            self._has_result = False
            self._fail(
                "No route is available. Check model profiles and quota state.",
                "Open Models",
            )
            self.routeChanged.emit()

        self._runner.start(operation, success, failure)
