"""Provider-neutral execution adapter protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from quotapilot.execution.models import ExecutionPlan, ExecutionResult


class ExecutionAdapter(Protocol):
    name: str
    provider: str

    def command_preview(
        self,
        model_id: str,
        effort: str | None,
        working_directory: Path,
    ) -> tuple[str, ...]: ...

    async def execute(self, plan: ExecutionPlan) -> ExecutionResult: ...
