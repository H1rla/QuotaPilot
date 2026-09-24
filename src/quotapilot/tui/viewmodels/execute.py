"""Application-owned execution state and exact-plan approval coordination."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from quotapilot.execution.models import ExecutionPlan, ExecutionResult
from quotapilot.services.execution import ExecutionService


@dataclass(frozen=True, slots=True)
class ExecuteState:
    status: str = "empty"
    plan: ExecutionPlan | None = None
    result: ExecutionResult | None = None
    message_id: str | None = None


class ExecuteViewModel:
    def __init__(self, service: ExecutionService | None) -> None:
        self._service = service
        self.state = ExecuteState()
        self.active = False
        self._task: asyncio.Task[ExecutionResult] | None = None

    async def prepare(
        self,
        task: str,
        directory: Path,
        *,
        dry_run: bool,
        publish: Callable[[ExecuteState], None] | None = None,
    ) -> ExecuteState:
        if self.active:
            return self.state
        self.active = True
        self.state = ExecuteState(status="planning")
        if publish is not None:
            publish(self.state)
        try:
            if self._service is None:
                raise RuntimeError("execution service unavailable")
            plan = await self._service.create_plan(
                task, working_directory=directory, dry_run=dry_run
            )
            self.state = ExecuteState(status="ready", plan=plan)
        except Exception:  # noqa: BLE001 - no raw task/provider error disclosure
            self.state = ExecuteState(status="error", message_id="execute.plan_error")
        finally:
            self.active = False
        return self.state

    async def run(
        self,
        approve: Callable[[ExecutionPlan], Awaitable[bool]],
        publish: Callable[[ExecuteState], None] | None = None,
    ) -> ExecuteState:
        plan = self.state.plan
        if self.active or plan is None or plan.dry_run:
            return self.state
        self.active = True
        self.state = ExecuteState(status="running", plan=plan)
        if publish is not None:
            publish(self.state)
        try:
            if self._service is None:
                raise RuntimeError("execution service unavailable")
            self._task = asyncio.create_task(
                self._service.run_plan(
                    plan,
                    approval_handler=approve,
                    plan_change_handler=approve,
                )
            )
            result = await self._task
            self.state = ExecuteState(status="result", plan=self.state.plan, result=result)
        except asyncio.CancelledError:
            self.state = ExecuteState(status="cancelled", plan=plan)
        except Exception:  # noqa: BLE001 - no raw adapter detail in UI
            self.state = ExecuteState(status="error", plan=plan, message_id="execute.run_error")
        finally:
            self._task = None
            self.active = False
        return self.state

    async def cancel(self) -> ExecuteState:
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            # The adapter handles cancellation by terminating and reaping its process.
            await asyncio.gather(task, return_exceptions=True)
        return self.state

    def awaiting_change(self, candidate: ExecutionPlan) -> ExecuteState:
        self.state = ExecuteState(
            status="awaiting_approval", plan=candidate, message_id="execute.changed_plan"
        )
        return self.state

    def resume(self) -> ExecuteState:
        self.state = ExecuteState(status="running", plan=self.state.plan)
        return self.state

    def clear(self) -> None:
        if not self.active:
            self.state = ExecuteState()
