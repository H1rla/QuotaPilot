"""Pure execution planning, strict policy, and authorization tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from quotapilot.budget.models import BudgetReport
from quotapilot.execution.errors import StaleExecutionBudgetError
from quotapilot.execution.escalation import EscalationEvaluator, NextAction
from quotapilot.execution.models import (
    ExecutionMode,
    ExecutionPolicy,
    ExecutionResult,
    ExecutionStatus,
    FailureClass,
)
from quotapilot.execution.planner import ExecutionPlanner
from quotapilot.execution.policy import ExecutionPolicyGate
from quotapilot.routing.models import (
    CandidateScore,
    ProfileSource,
    QuotaPressureSource,
    RecommendationConfidence,
    RoutingRecommendation,
    RoutingStep,
    TaskClass,
    TaskProfile,
)

NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)


def _profile(*, low_risk: bool = True) -> TaskProfile:
    return TaskProfile(
        summary="Synthetic private task payload",
        complexity=0.1 if low_risk else 0.9,
        ambiguity=0.1 if low_risk else 0.8,
        failure_cost=0.1 if low_risk else 0.9,
        verifiability=0.9 if low_risk else 0.1,
        context_demand=0.2,
        latency_sensitivity=0.5,
        task_class=TaskClass.MECHANICAL if low_risk else TaskClass.ARCHITECTURE,
        profile_source=ProfileSource.EXPLICIT,
    )


def _recommendation(*, low_risk: bool = True) -> RoutingRecommendation:
    profile = _profile(low_risk=low_risk)
    return RoutingRecommendation(
        task_profile=profile,
        difficulty_score=0.1 if low_risk else 0.9,
        required_power=0.2 if low_risk else 0.9,
        capability_floor=0.1 if low_risk else 0.85,
        effort_demand=0.2 if low_risk else 0.9,
        quota_pressure=0.35,
        quota_pressure_source=QuotaPressureSource.BUDGET_REPORT,
        binding_pool_id="weekly",
        selected_model_id="base",
        selected_effort="normal",
        candidate_scores=(
            CandidateScore(
                model_id="base",
                selectable=True,
                relative_power=0.7,
                relative_cost=0.4,
                relative_latency=0.3,
                effective_cost=0.4,
                effective_latency=0.3,
                quality_score=0.8,
                quota_penalty=0.1,
                latency_penalty=0.1,
                overcapability_penalty=0.0,
                utility=0.6,
                eligible=True,
            ),
        ),
        escalation_path=(RoutingStep(model_id="strong", effort="deep", reason="stronger"),),
        alternatives=(),
        explanation=("deterministic synthetic recommendation",),
        warnings=(),
        confidence=RecommendationConfidence.HIGH,
    )


def _budget(*, age: float = 0.0, pressure: float = 0.35) -> BudgetReport:
    return BudgetReport(
        captured_at=NOW,
        evaluated_at=NOW,
        snapshot_age_seconds=age,
        is_stale=age > 900,
        reserve_fraction=0.1,
        timezone="UTC",
        pools=(),
        effective_pressure=pressure,
        binding_pool_id="weekly",
    )


def _plan(tmp_path: Path, policy: ExecutionPolicy | None = None):
    policy = policy or ExecutionPolicy()
    return ExecutionPlanner(policy, id_factory=lambda: "execution-1").build(
        _recommendation(),
        _budget(),
        provider="test-provider",
        task_payload="Synthetic private task payload",
        working_directory=tmp_path,
        dry_run=False,
        adapter_name="fake",
        command_preview=("fake", "exec"),
        planned_at=NOW,
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_attempts": "3"}, "valid integer"),
        ({"require_fresh_budget": 1}, "valid boolean"),
        ({"timeout_second": 5}, "Extra inputs"),
        ({"max_attempts": 1, "max_same_step_retries": 1}, "smaller"),
        (
            {"retryable_failures": (FailureClass.AUTHENTICATION,)},
            "non-retryable",
        ),
    ],
)
def test_execution_policy_is_strict(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        ExecutionPolicy.model_validate(kwargs)


def test_default_requires_confirmation_and_dry_run_never_does() -> None:
    gate = ExecutionPolicyGate(ExecutionPolicy())

    assert gate.decide(_profile(), dry_run=False, is_escalation=False).requires_confirmation
    assert not gate.decide(_profile(), dry_run=True, is_escalation=False).requires_confirmation


def test_low_risk_auto_mode_does_not_bypass_high_risk_confirmation() -> None:
    gate = ExecutionPolicyGate(ExecutionPolicy(mode=ExecutionMode.AUTO_FOR_LOW_RISK))

    assert not gate.decide(
        _profile(low_risk=True), dry_run=False, is_escalation=False
    ).requires_confirmation
    assert gate.decide(
        _profile(low_risk=False), dry_run=False, is_escalation=False
    ).requires_confirmation


def test_plan_json_is_auditable_without_raw_task(tmp_path: Path) -> None:
    plan = ExecutionPlanner(ExecutionPolicy(), id_factory=lambda: "execution-1").build(
        _recommendation(),
        _budget(),
        provider="test-provider",
        task_payload="Synthetic private task payload",
        working_directory=tmp_path,
        dry_run=True,
        adapter_name="fake",
        command_preview=("fake", "exec"),
        planned_at=NOW,
    )
    payload = plan.model_dump_json()

    assert plan.task_class is TaskClass.MECHANICAL
    assert plan.task_payload == "Synthetic private task payload"
    assert "Synthetic private task payload" not in payload
    assert "task_payload" not in payload
    assert "task_profile" not in payload
    assert '"task_class":"mechanical"' in payload
    assert "sha256:" in payload


def test_stale_budget_is_rejected_before_plan_creation(tmp_path: Path) -> None:
    with pytest.raises(StaleExecutionBudgetError, match="freshness"):
        ExecutionPlanner(ExecutionPolicy()).build(
            _recommendation(),
            _budget(age=301),
            provider="test-provider",
            task_payload="Synthetic private task payload",
            working_directory=tmp_path,
            dry_run=False,
            adapter_name="fake",
            command_preview=("fake", "exec"),
            planned_at=NOW,
        )


def test_retry_and_escalation_are_distinct_and_bounded(tmp_path: Path) -> None:
    ids = iter(("initial", "retry", "escalated"))
    policy = ExecutionPolicy(
        retryable_failures=(FailureClass.TRANSPORT,),
        escalation_failures=(FailureClass.TRANSPORT,),
    )
    planner = ExecutionPlanner(policy, id_factory=lambda: next(ids))
    plan = planner.build(
        _recommendation(),
        _budget(),
        provider="test-provider",
        task_payload="Synthetic private task payload",
        working_directory=tmp_path,
        dry_run=False,
        adapter_name="fake",
        command_preview=("fake", "exec"),
        planned_at=NOW,
    )
    failure = ExecutionResult(
        execution_id=plan.execution_id,
        task_hash=plan.task_hash,
        started_at=NOW,
        finished_at=NOW,
        model_id=plan.model_id,
        effort=plan.effort,
        status=ExecutionStatus.FAILED,
        failure_class=FailureClass.TRANSPORT,
    )
    evaluator = EscalationEvaluator(policy)

    assert evaluator.decide(
        plan, failure, total_attempts=1, same_step_retries=0
    ).action is NextAction.RETRY
    retried = planner.retry(plan)
    assert retried.model_id == plan.model_id
    assert retried.effort == plan.effort
    assert evaluator.decide(
        retried, failure, total_attempts=2, same_step_retries=1
    ).action is NextAction.ESCALATE
    escalated = planner.escalate(
        retried,
        retried.escalation_path[0],
        _budget(),
        command_preview=("fake", "strong"),
        planned_at=NOW,
    )
    assert (escalated.model_id, escalated.effort) == ("strong", "deep")
    assert escalated.attempt_number == 3
