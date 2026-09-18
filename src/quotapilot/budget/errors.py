"""Typed failures for invalid Budget Engine caller contracts."""


class BudgetError(Exception):
    """Base class for exceptional budget failures."""


class BudgetEvaluationError(BudgetError):
    """Evaluation input violates an invariant required for deterministic output."""
