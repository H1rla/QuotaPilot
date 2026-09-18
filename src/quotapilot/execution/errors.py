"""Typed failures at the controlled-execution boundary."""


class ExecutionError(Exception):
    """Base class for planning, policy, revalidation, and adapter failures."""


class ExecutionPlanningError(ExecutionError):
    """A safe execution plan could not be constructed."""


class NoExecutionSnapshotError(ExecutionPlanningError):
    """Dry-run planning has no persisted snapshot to consume."""


class StaleExecutionBudgetError(ExecutionPlanningError):
    """The available budget is too old for the configured execution policy."""


class ExecutionAdapterError(ExecutionError):
    """An execution adapter violated its protocol or could not be used."""
