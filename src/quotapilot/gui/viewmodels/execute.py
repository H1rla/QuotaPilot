"""Deliberate execution-plan and approval view model."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, Signal, Slot

from quotapilot.execution.models import ExecutionPlan, ExecutionResult

from ..async_runner import AsyncRunner
from ..dependencies import GuiDependencies
from ..mappers import map_execution_plan, map_execution_result
from .base import BaseViewModel

_EMPTY_PLAN: dict[str, Any] = {
    "model": "Unavailable",
    "effort": "Unavailable",
    "workingDirectory": "Unavailable",
    "quotaState": "Unknown",
    "approval": "Unknown",
    "timeout": "Unknown",
    "maxAttempts": 0,
    "dryRun": True,
    "escalation": [],
}
_EMPTY_RESULT: dict[str, Any] = {
    "status": "UNKNOWN",
    "attempts": 0,
    "failureClass": "None",
    "message": "",
}


class ExecuteViewModel(BaseViewModel):
    executionChanged = Signal()

    def __init__(self, dependencies: GuiDependencies, runner: AsyncRunner) -> None:
        super().__init__()
        self._dependencies = dependencies
        self._runner = runner
        self._plan: ExecutionPlan | None = None
        self._plan_data: dict[str, Any] = dict(_EMPTY_PLAN)
        self._result_data: dict[str, Any] = dict(_EMPTY_RESULT)
        self._has_result = False

    @Property(dict, notify=executionChanged)
    def plan(self) -> dict[str, Any]:
        return self._plan_data

    @Property(dict, notify=executionChanged)
    def result(self) -> dict[str, Any]:
        return self._result_data

    @Property(bool, notify=executionChanged)
    def hasPlan(self) -> bool:  # noqa: N802
        return self._plan is not None

    @Property(bool, notify=executionChanged)
    def hasResult(self) -> bool:  # noqa: N802
        return self._has_result

    @Slot(str, str, bool)
    def prepare(self, task: str, working_directory: str, dry_run: bool) -> None:
        if self.busy:
            return
        if not task.strip():
            self._fail("Analyze a task before creating an execution plan.", "Open Route")
            return
        self._begin()
        self._plan = None
        self._plan_data = dict(_EMPTY_PLAN)
        self._result_data = dict(_EMPTY_RESULT)
        self._has_result = False
        self.executionChanged.emit()

        async def operation() -> ExecutionPlan:
            return await self._dependencies.execution_service.create_plan(
                task,
                working_directory=Path(working_directory).expanduser(),
                dry_run=dry_run,
            )

        def success(value: object) -> None:
            if not isinstance(value, ExecutionPlan):
                self._fail("Execution plan could not be created.", "Retry")
                return
            self._plan = value
            self._plan_data = map_execution_plan(value)
            self._finish()
            self.executionChanged.emit()

        def failure(_error: Exception) -> None:
            self._fail(
                "Execution plan is unavailable. Verify the directory and quota freshness.",
                "Retry",
            )
            self.executionChanged.emit()

        self._runner.start(operation, success, failure)

    @Slot()
    def run(self) -> None:
        if self.busy or self._plan is None:
            return
        plan = self._plan
        self._begin()

        async def operation() -> ExecutionResult:
            async def approve(candidate: ExecutionPlan) -> bool:
                # The user clicked the focused confirmation action for this exact plan.
                return candidate.execution_id == plan.execution_id

            return await self._dependencies.execution_service.run_plan(
                plan,
                approval_handler=approve,
            )

        def success(value: object) -> None:
            if isinstance(value, ExecutionResult):
                self._result_data = map_execution_result(value)
                self._has_result = True
            self._finish()
            self.executionChanged.emit()

        def failure(_error: Exception) -> None:
            self._fail("Execution failed before a safe result was available.", "Retry")
            self.executionChanged.emit()

        self._runner.start(operation, success, failure)

    @Slot()
    def cancel(self) -> None:
        self._plan = None
        self._plan_data = dict(_EMPTY_PLAN)
        self._result_data = dict(_EMPTY_RESULT)
        self._has_result = False
        self.clearError()
        self.executionChanged.emit()
