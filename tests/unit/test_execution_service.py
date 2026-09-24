"""Controlled execution service state-machine and revalidation tests."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from pathlib import Path

import pytest

from quotapilot.budget.models import BudgetReport
from quotapilot.domain.account import AccountInfo
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.model import AIModel
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.execution.errors import (
    ExecutionAdapterError,
    ExecutionPlanningError,
    NoExecutionSnapshotError,
    StaleExecutionBudgetError,
)
from quotapilot.execution.models import (
    ExecutionMode,
    ExecutionPlan,
    ExecutionPolicy,
    ExecutionResult,
    ExecutionStatus,
    FailureClass,
    execution_event,
)
from quotapilot.execution.planner import ExecutionPlanner
from quotapilot.routing.errors import NoRoutableModelError
from quotapilot.routing.models import (
    CandidateScore,
    ProfileSource,
    QuotaPressureSource,
    RecommendationConfidence,
    RoutingRecommendation,
    RoutingStep,
    TaskClass,
    TaskProfile,
    TaskProfileOverrides,
)
from quotapilot.services.execution import ExecutionService
from quotapilot.services.routing import RoutingContext

NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)
TASK = "Synthetic bounded implementation task"


def _model(
    model_id: str,
    *,
    selectable: bool = True,
    efforts: tuple[str, ...] = ("normal", "deep"),
    power: float | None = None,
) -> AIModel:
    return AIModel(
        id=model_id,
        provider="test-provider",
        selectable=selectable,
        supported_efforts=efforts,
        effort_order=efforts,
        relative_power=(0.7 if model_id == "base" else 0.95) if power is None else power,
        relative_cost=0.4,
        relative_latency=0.3,
    )


def _profile() -> TaskProfile:
    return TaskProfile(
        summary=TASK,
        complexity=0.5,
        ambiguity=0.4,
        failure_cost=0.4,
        verifiability=0.7,
        context_demand=0.5,
        latency_sensitivity=0.3,
        task_class=TaskClass.LOCAL_IMPLEMENTATION,
        profile_source=ProfileSource.EXPLICIT,
    )


def _recommendation(
    *,
    path: tuple[RoutingStep, ...] = (
        RoutingStep(model_id="strong", effort="deep", reason="stronger capability"),
    ),
) -> RoutingRecommendation:
    return RoutingRecommendation(
        task_profile=_profile(),
        difficulty_score=0.5,
        required_power=0.6,
        capability_floor=0.5,
        effort_demand=0.6,
        quota_pressure=0.35,
        quota_pressure_source=QuotaPressureSource.BUDGET_REPORT,
        binding_pool_id="weekly",
        selected_model_id="base",
        selected_effort="normal",
        candidate_scores=(
            CandidateScore(model_id="base", selectable=True, eligible=True),
            CandidateScore(model_id="strong", selectable=True, eligible=True),
        ),
        escalation_path=path,
        alternatives=(),
        explanation=("synthetic",),
        warnings=(),
        confidence=RecommendationConfidence.HIGH,
    )


def _context(
    *,
    pressure: float = 0.35,
    age: float = 0.0,
    models: tuple[AIModel, ...] | None = None,
    path: tuple[RoutingStep, ...] | None = None,
) -> RoutingContext:
    capabilities = CapabilitySet(models=models or (_model("base"), _model("strong")))
    budget = BudgetReport(
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
    recommendation = _recommendation() if path is None else _recommendation(path=path)
    return RoutingContext(
        provider="test-provider",
        recommendation=recommendation,
        budget_report=budget,
        capabilities=capabilities,
        snapshot_captured_at=NOW,
    )


def _snapshot() -> UsageSnapshot:
    return UsageSnapshot(
        account=AccountInfo(
            provider="test-provider",
            capabilities=CapabilitySet(models=(_model("base"), _model("strong"))),
            observed_at=NOW,
        ),
        quota_pools=(),
        quota_bindings=(),
        captured_at=NOW,
    )


class _Provider:
    def __init__(self) -> None:
        self.capture_count = 0

    async def capture_usage(self) -> UsageSnapshot:
        self.capture_count += 1
        return _snapshot()


class _Contexts:
    def __init__(
        self,
        latest: RoutingContext | None,
        live: list[RoutingContext] | None = None,
    ) -> None:
        self.latest = latest
        self.live = deque(live or [])

    async def recommend_latest_context(
        self,
        summary: str,
        *,
        now: datetime,
        overrides: TaskProfileOverrides | None = None,
        provider: str | None = None,
    ) -> RoutingContext | None:
        del summary, now, overrides, provider
        return self.latest

    def recommend_snapshot(
        self,
        snapshot: UsageSnapshot,
        summary: str,
        *,
        now: datetime,
        overrides: TaskProfileOverrides | None = None,
    ) -> RoutingContext:
        del snapshot, summary, now, overrides
        return self.live.popleft()

    def recommend_profile_snapshot(
        self,
        snapshot: UsageSnapshot,
        profile: TaskProfile,
        *,
        now: datetime,
    ) -> RoutingContext:
        del snapshot, now
        assert profile == _profile()
        return self.live.popleft()


class _Adapter:
    name = "fake"
    provider = "test-provider"

    def __init__(self, outcomes: list[FailureClass | None]) -> None:
        self.outcomes = deque(outcomes)
        self.execute_count = 0

    def command_preview(
        self, model_id: str, effort: str | None, working_directory: Path
    ) -> tuple[str, ...]:
        return ("fake", model_id, effort or "default", str(working_directory))

    async def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        self.execute_count += 1
        failure = self.outcomes.popleft()
        if failure is None:
            status = ExecutionStatus.SUCCEEDED
        elif failure is FailureClass.USER_CANCELLED:
            status = ExecutionStatus.CANCELLED
        else:
            status = ExecutionStatus.FAILED
        return ExecutionResult(
            execution_id=plan.execution_id,
            task_hash=plan.task_hash,
            started_at=NOW,
            finished_at=NOW,
            model_id=plan.model_id,
            effort=plan.effort,
            status=status,
            exit_code=0 if failure is None else 1,
            failure_class=failure,
            attempt_count=1,
            events=(
                execution_event(plan, ExecutionStatus.RUNNING, NOW),
                execution_event(plan, status, NOW),
            ),
        )


class _StaleProfileContexts(_Contexts):
    def recommend_profile_snapshot(
        self,
        snapshot: UsageSnapshot,
        profile: TaskProfile,
        *,
        now: datetime,
    ) -> RoutingContext:
        del snapshot, profile, now
        raise NoRoutableModelError("profile became stale")


def _service(
    tmp_path: Path,
    contexts: _Contexts,
    adapter: _Adapter,
    *,
    policy: ExecutionPolicy | None = None,
) -> tuple[ExecutionService, _Provider]:
    del tmp_path
    selected_policy = policy or ExecutionPolicy()
    provider = _Provider()
    ids = iter(f"execution-{index}" for index in range(1, 20))
    service = ExecutionService(
        provider,
        contexts,
        adapter,
        ExecutionPlanner(selected_policy, id_factory=lambda: next(ids)),
        selected_policy,
        clock=lambda: NOW,
    )
    return service, provider


async def _approve(_plan: ExecutionPlan) -> bool:
    return True


@pytest.mark.asyncio
async def test_dry_run_never_captures_live_or_invokes_adapter(tmp_path: Path) -> None:
    adapter = _Adapter([])
    service, provider = _service(tmp_path, _Contexts(_context()), adapter)

    plan = await service.create_plan(TASK, working_directory=tmp_path, dry_run=True)
    result = await service.run_plan(plan)

    assert result.status is ExecutionStatus.DRY_RUN
    assert provider.capture_count == 0
    assert adapter.execute_count == 0


@pytest.mark.asyncio
async def test_dry_run_requires_a_fresh_persisted_snapshot(tmp_path: Path) -> None:
    service, _provider = _service(tmp_path, _Contexts(None), _Adapter([]))
    with pytest.raises(NoExecutionSnapshotError):
        await service.create_plan(TASK, working_directory=tmp_path, dry_run=True)

    stale_service, _provider = _service(
        tmp_path, _Contexts(_context(age=301)), _Adapter([])
    )
    with pytest.raises(StaleExecutionBudgetError):
        await stale_service.create_plan(TASK, working_directory=tmp_path, dry_run=True)


@pytest.mark.asyncio
async def test_default_policy_waits_for_explicit_approval(tmp_path: Path) -> None:
    adapter = _Adapter([None])
    service, provider = _service(
        tmp_path, _Contexts(_context(), [_context()]), adapter
    )
    plan = await service.create_plan(TASK, working_directory=tmp_path, dry_run=False)

    result = await service.run_plan(plan)

    assert result.status is ExecutionStatus.AWAITING_APPROVAL
    assert provider.capture_count == 0
    assert adapter.execute_count == 0


@pytest.mark.asyncio
async def test_tampered_plan_is_rejected_before_capture_or_execution(tmp_path: Path) -> None:
    adapter = _Adapter([None])
    service, provider = _service(
        tmp_path, _Contexts(_context(), [_context()]), adapter
    )
    plan = await service.create_plan(TASK, working_directory=tmp_path, dry_run=False)

    with pytest.raises(ExecutionPlanningError, match="digest"):
        await service.run_plan(
            plan.model_copy(update={"task_payload": "different task"}),
            approval_handler=_approve,
        )
    with pytest.raises(ExecutionAdapterError, match="command preview"):
        await service.run_plan(
            plan.model_copy(update={"command_preview": ("deceptive",)}),
            approval_handler=_approve,
        )

    assert provider.capture_count == 0
    assert adapter.execute_count == 0


@pytest.mark.asyncio
async def test_success_revalidates_quota_and_capabilities_after_approval(
    tmp_path: Path,
) -> None:
    adapter = _Adapter([None])
    service, provider = _service(
        tmp_path, _Contexts(_context(), [_context()]), adapter
    )
    plan = await service.create_plan(TASK, working_directory=tmp_path, dry_run=False)

    result = await service.run_plan(plan, approval_handler=_approve)

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.attempt_count == 1
    assert provider.capture_count == 1
    assert adapter.execute_count == 1


@pytest.mark.asyncio
async def test_material_quota_change_requires_replan_without_execution(tmp_path: Path) -> None:
    adapter = _Adapter([None])
    service, provider = _service(
        tmp_path, _Contexts(_context(), [_context(pressure=0.7)]), adapter
    )
    plan = await service.create_plan(TASK, working_directory=tmp_path, dry_run=False)

    result = await service.run_plan(plan, approval_handler=_approve)

    assert result.status is ExecutionStatus.QUOTA_CHANGED
    assert result.failure_class is FailureClass.QUOTA
    assert provider.capture_count == 1
    assert adapter.execute_count == 0


@pytest.mark.asyncio
async def test_removed_model_or_unsupported_effort_denies_execution(tmp_path: Path) -> None:
    for models in (
        (_model("strong"),),
        (_model("base", efforts=("deep",)), _model("strong")),
        (_model("base", selectable=False), _model("strong")),
    ):
        adapter = _Adapter([None])
        service, _provider = _service(
            tmp_path, _Contexts(_context(), [_context(models=models)]), adapter
        )
        plan = await service.create_plan(TASK, working_directory=tmp_path, dry_run=False)

        result = await service.run_plan(plan, approval_handler=_approve)

        assert result.status is ExecutionStatus.CAPABILITY_CHANGED
        assert adapter.execute_count == 0


@pytest.mark.asyncio
async def test_newly_stale_profile_is_a_structured_capability_change(tmp_path: Path) -> None:
    adapter = _Adapter([None])
    service, _provider = _service(
        tmp_path, _StaleProfileContexts(_context()), adapter
    )
    plan = await service.create_plan(TASK, working_directory=tmp_path, dry_run=False)

    result = await service.run_plan(plan, approval_handler=_approve)

    assert result.status is ExecutionStatus.CAPABILITY_CHANGED
    assert result.failure_class is FailureClass.VALIDATION
    assert adapter.execute_count == 0


@pytest.mark.asyncio
async def test_transport_retry_is_bounded_and_reuses_same_plan_approval(
    tmp_path: Path,
) -> None:
    adapter = _Adapter([FailureClass.TRANSPORT, None])
    service, provider = _service(
        tmp_path, _Contexts(_context(), [_context(), _context()]), adapter
    )
    approvals = 0

    async def approve(_plan: ExecutionPlan) -> bool:
        nonlocal approvals
        approvals += 1
        return True

    plan = await service.create_plan(TASK, working_directory=tmp_path, dry_run=False)
    result = await service.run_plan(plan, approval_handler=approve)

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.attempt_count == 2
    assert result.retry_count == 1
    assert result.escalation_count == 0
    assert provider.capture_count == 2
    assert adapter.execute_count == 2
    assert approvals == 1


@pytest.mark.asyncio
async def test_quota_is_rechecked_before_escalation_and_can_stop_it(
    tmp_path: Path,
) -> None:
    adapter = _Adapter([FailureClass.VALIDATION, None])
    service, provider = _service(
        tmp_path,
        _Contexts(_context(), [_context(), _context(pressure=1.0)]),
        adapter,
    )
    plan = await service.create_plan(TASK, working_directory=tmp_path, dry_run=False)

    result = await service.run_plan(plan, approval_handler=_approve)

    assert result.status is ExecutionStatus.QUOTA_CHANGED
    assert result.attempt_count == 1
    assert result.escalation_count == 1
    assert provider.capture_count == 2
    assert adapter.execute_count == 1


@pytest.mark.asyncio
async def test_total_attempt_limit_stops_before_escalation(tmp_path: Path) -> None:
    policy = ExecutionPolicy(max_attempts=1, max_same_step_retries=0)
    adapter = _Adapter([FailureClass.VALIDATION])
    service, provider = _service(
        tmp_path, _Contexts(_context(), [_context()]), adapter, policy=policy
    )
    plan = await service.create_plan(TASK, working_directory=tmp_path, dry_run=False)

    result = await service.run_plan(plan, approval_handler=_approve)

    assert result.status is ExecutionStatus.FAILED
    assert result.attempt_count == 1
    assert result.escalation_count == 0
    assert provider.capture_count == 1
    assert adapter.execute_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "expected_status"),
    [
        (FailureClass.AUTHENTICATION, ExecutionStatus.FAILED),
        (FailureClass.QUOTA, ExecutionStatus.FAILED),
        (FailureClass.TIMEOUT, ExecutionStatus.FAILED),
        (FailureClass.USER_CANCELLED, ExecutionStatus.CANCELLED),
    ],
)
async def test_authentication_and_cancellation_never_retry_or_escalate(
    tmp_path: Path,
    failure: FailureClass,
    expected_status: ExecutionStatus,
) -> None:
    adapter = _Adapter([failure])
    service, provider = _service(
        tmp_path, _Contexts(_context(), [_context()]), adapter
    )
    plan = await service.create_plan(TASK, working_directory=tmp_path, dry_run=False)

    result = await service.run_plan(plan, approval_handler=_approve)

    assert result.status is expected_status
    assert result.attempt_count == 1
    assert result.retry_count == 0
    assert result.escalation_count == 0
    assert provider.capture_count == 1
    assert adapter.execute_count == 1


@pytest.mark.asyncio
async def test_validation_failure_follows_route_escalation_with_new_approval(
    tmp_path: Path,
) -> None:
    adapter = _Adapter([FailureClass.VALIDATION, None])
    service, provider = _service(
        tmp_path, _Contexts(_context(), [_context(), _context()]), adapter
    )
    approved_models: list[str] = []

    async def approve(plan: ExecutionPlan) -> bool:
        approved_models.append(plan.model_id)
        return True

    plan = await service.create_plan(TASK, working_directory=tmp_path, dry_run=False)
    result = await service.run_plan(plan, approval_handler=approve)

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.model_id == "strong"
    assert result.attempt_count == 2
    assert result.escalation_count == 1
    assert approved_models == ["base", "strong"]
    assert provider.capture_count == 2


@pytest.mark.asyncio
async def test_interactive_plan_change_requires_new_approval_even_in_auto_mode(
    tmp_path: Path,
) -> None:
    policy = ExecutionPolicy(
        mode=ExecutionMode.AUTO_FOR_LOW_RISK,
        low_risk_max_complexity=1.0,
        low_risk_max_ambiguity=1.0,
        low_risk_max_failure_cost=1.0,
        low_risk_min_verifiability=0.0,
    )
    adapter = _Adapter([FailureClass.VALIDATION, None])
    service, _provider = _service(
        tmp_path, _Contexts(_context(), [_context()]), adapter, policy=policy
    )
    changed: list[ExecutionPlan] = []

    async def reject_changed(candidate: ExecutionPlan) -> bool:
        changed.append(candidate)
        return False

    plan = await service.create_plan(TASK, working_directory=tmp_path, dry_run=False)
    result = await service.run_plan(
        plan, approval_handler=reject_changed, plan_change_handler=reject_changed
    )

    assert result.status is ExecutionStatus.DENIED
    assert adapter.execute_count == 1
    assert len(changed) == 1
    assert changed[0].model_id == "strong"
    assert changed[0] != plan


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "models",
    [
        (_model("base"),),
        (_model("base"), _model("strong", efforts=("normal",))),
    ],
)
async def test_changed_escalation_capability_stops_before_second_attempt(
    tmp_path: Path,
    models: tuple[AIModel, ...],
) -> None:
    adapter = _Adapter([FailureClass.VALIDATION, None])
    service, provider = _service(
        tmp_path,
        _Contexts(_context(), [_context(), _context(models=models)]),
        adapter,
    )
    plan = await service.create_plan(TASK, working_directory=tmp_path, dry_run=False)

    result = await service.run_plan(plan, approval_handler=_approve)

    assert result.status is ExecutionStatus.CAPABILITY_CHANGED
    assert result.attempt_count == 1
    assert provider.capture_count == 2
    assert adapter.execute_count == 1


@pytest.mark.asyncio
async def test_escalation_disabled_stops_after_failure(tmp_path: Path) -> None:
    policy = ExecutionPolicy(allow_escalation=False)
    adapter = _Adapter([FailureClass.VALIDATION])
    service, provider = _service(
        tmp_path, _Contexts(_context(), [_context()]), adapter, policy=policy
    )
    plan = await service.create_plan(TASK, working_directory=tmp_path, dry_run=False)

    result = await service.run_plan(plan, approval_handler=_approve)

    assert result.status is ExecutionStatus.FAILED
    assert result.escalation_count == 0
    assert result.escalation_recommended
    assert result.next_step is not None
    assert provider.capture_count == 1


@pytest.mark.asyncio
async def test_never_execute_policy_denies_before_live_capture(tmp_path: Path) -> None:
    policy = ExecutionPolicy(mode=ExecutionMode.NEVER_EXECUTE)
    adapter = _Adapter([None])
    service, provider = _service(
        tmp_path, _Contexts(_context(), [_context()]), adapter, policy=policy
    )
    plan = await service.create_plan(TASK, working_directory=tmp_path, dry_run=False)

    result = await service.run_plan(plan, approval_handler=_approve)

    assert result.status is ExecutionStatus.DENIED
    assert provider.capture_count == 0
    assert adapter.execute_count == 0
