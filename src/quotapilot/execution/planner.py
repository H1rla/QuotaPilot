"""Pure-ish conversion from advisory routing output to an inspectable plan."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from quotapilot.budget.models import BudgetReport
from quotapilot.execution.errors import ExecutionPlanningError, StaleExecutionBudgetError
from quotapilot.execution.models import ExecutionPlan, ExecutionPolicy
from quotapilot.execution.policy import ExecutionPolicyGate
from quotapilot.routing.models import RoutingRecommendation, RoutingStep


class ExecutionPlanner:
    """Construct plans without provider, persistence, or subprocess access."""

    def __init__(
        self,
        policy: ExecutionPolicy,
        *,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.policy = policy
        self._gate = ExecutionPolicyGate(policy)
        self._id_factory = id_factory or (lambda: str(uuid4()))

    def build(
        self,
        recommendation: RoutingRecommendation,
        budget: BudgetReport,
        *,
        provider: str,
        task_payload: str,
        working_directory: Path,
        dry_run: bool,
        adapter_name: str,
        command_preview: tuple[str, ...],
        planned_at: datetime,
    ) -> ExecutionPlan:
        self._validate_budget(budget)
        if task_payload != recommendation.task_profile.summary:
            raise ExecutionPlanningError("task payload does not match recommendation")
        decision = self._gate.decide(
            recommendation.task_profile,
            dry_run=dry_run,
            is_escalation=False,
        )
        task_hash = _digest(task_payload)
        link = _recommendation_link(recommendation, task_hash)
        return ExecutionPlan(
            execution_id=self._id_factory(),
            provider=provider,
            model_id=recommendation.selected_model_id,
            effort=recommendation.selected_effort,
            initial_model_id=recommendation.selected_model_id,
            initial_effort=recommendation.selected_effort,
            task_payload=task_payload,
            task_hash=task_hash,
            task_profile=recommendation.task_profile,
            task_class=recommendation.task_profile.task_class,
            recommendation_link=link,
            attempt_number=1,
            escalation_index=0,
            max_attempts=self.policy.max_attempts,
            dry_run=dry_run,
            requires_confirmation=decision.requires_confirmation,
            working_directory=working_directory.resolve(strict=True),
            timeout_seconds=self.policy.timeout_seconds,
            adapter_name=adapter_name,
            command_preview=command_preview,
            quota_snapshot_captured_at=budget.captured_at,
            budget_pressure=budget.effective_pressure,
            binding_pool_id=budget.binding_pool_id,
            planned_at=planned_at,
            escalation_path=recommendation.escalation_path,
            warnings=tuple(budget.warnings),
        )

    def retry(self, plan: ExecutionPlan) -> ExecutionPlan:
        if plan.attempt_number >= plan.max_attempts:
            raise ExecutionPlanningError("maximum total attempts reached")
        return plan.model_copy(
            update={
                "execution_id": self._id_factory(),
                "attempt_number": plan.attempt_number + 1,
                "requires_confirmation": False,
            }
        )

    def validate_initial(self, plan: ExecutionPlan) -> None:
        """Reject a plan whose in-memory payload or policy binding was altered."""
        if plan.task_hash != _digest(plan.task_payload):
            raise ExecutionPlanningError("execution plan task digest does not match payload")
        if (
            plan.task_payload != plan.task_profile.summary
            or plan.task_class is not plan.task_profile.task_class
        ):
            raise ExecutionPlanningError("execution plan task profile does not match payload")
        if plan.attempt_number != 1 or plan.escalation_index != 0:
            raise ExecutionPlanningError("run_plan requires an initial execution plan")
        if (
            plan.max_attempts != self.policy.max_attempts
            or plan.timeout_seconds != self.policy.timeout_seconds
        ):
            raise ExecutionPlanningError("execution plan does not match current policy")

    def escalate(
        self,
        plan: ExecutionPlan,
        step: RoutingStep,
        budget: BudgetReport,
        *,
        command_preview: tuple[str, ...],
        planned_at: datetime,
    ) -> ExecutionPlan:
        if plan.attempt_number >= plan.max_attempts:
            raise ExecutionPlanningError("maximum total attempts reached")
        self._validate_budget(budget)
        decision = self._gate.decide(
            plan.task_profile,
            dry_run=False,
            is_escalation=True,
        )
        return plan.model_copy(
            update={
                "execution_id": self._id_factory(),
                "model_id": step.model_id,
                "effort": step.effort,
                "attempt_number": plan.attempt_number + 1,
                "escalation_index": plan.escalation_index + 1,
                "requires_confirmation": decision.requires_confirmation,
                "command_preview": command_preview,
                "quota_snapshot_captured_at": budget.captured_at,
                "budget_pressure": budget.effective_pressure,
                "binding_pool_id": budget.binding_pool_id,
                "planned_at": planned_at,
                "warnings": tuple(budget.warnings),
            }
        )

    def _validate_budget(self, budget: BudgetReport) -> None:
        if not self.policy.require_fresh_budget:
            return
        if (
            budget.snapshot_age_seconds < 0
            or budget.snapshot_age_seconds > self.policy.max_budget_age_seconds
        ):
            raise StaleExecutionBudgetError("execution budget is outside the freshness limit")


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _recommendation_link(
    recommendation: RoutingRecommendation,
    task_hash: str,
) -> str:
    safe_binding = {
        "task_hash": task_hash,
        "model_id": recommendation.selected_model_id,
        "effort": recommendation.selected_effort,
        "required_power": recommendation.required_power,
        "capability_floor": recommendation.capability_floor,
        "quota_pressure": recommendation.quota_pressure,
        "quota_pressure_source": recommendation.quota_pressure_source.value,
        "binding_pool_id": recommendation.binding_pool_id,
        "escalation_path": [
            {"model_id": step.model_id, "effort": step.effort}
            for step in recommendation.escalation_path
        ],
    }
    encoded = json.dumps(safe_binding, sort_keys=True, separators=(",", ":"))
    return _digest(encoded)
