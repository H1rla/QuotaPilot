"""Controlled orchestration from advisory route to bounded external execution."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from quotapilot.capabilities.errors import CapabilityProfileError
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.execution.adapters.base import ExecutionAdapter
from quotapilot.execution.errors import (
    ExecutionAdapterError,
    NoExecutionSnapshotError,
    StaleExecutionBudgetError,
)
from quotapilot.execution.escalation import EscalationEvaluator, NextAction
from quotapilot.execution.models import (
    ExecutionEvent,
    ExecutionPlan,
    ExecutionPolicy,
    ExecutionResult,
    ExecutionStatus,
    FailureClass,
    execution_event,
)
from quotapilot.execution.planner import ExecutionPlanner
from quotapilot.execution.policy import ExecutionPolicyGate
from quotapilot.routing.errors import RoutingError
from quotapilot.routing.models import RoutingStep, TaskProfile, TaskProfileOverrides
from quotapilot.services.routing import RoutingContext

Clock = Callable[[], datetime]
ApprovalHandler = Callable[[ExecutionPlan], Awaitable[bool]]


class _UsageCapture(Protocol):
    async def capture_usage(self) -> UsageSnapshot: ...


class _RoutingContextSource(Protocol):
    async def recommend_latest_context(
        self,
        summary: str,
        *,
        now: datetime,
        overrides: TaskProfileOverrides | None = None,
        provider: str | None = None,
    ) -> RoutingContext | None: ...

    def recommend_snapshot(
        self,
        snapshot: UsageSnapshot,
        summary: str,
        *,
        now: datetime,
        overrides: TaskProfileOverrides | None = None,
    ) -> RoutingContext: ...

    def recommend_profile_snapshot(
        self,
        snapshot: UsageSnapshot,
        profile: TaskProfile,
        *,
        now: datetime,
    ) -> RoutingContext: ...


@dataclass(frozen=True, slots=True)
class _Revalidated:
    context: RoutingContext


class ExecutionService:
    """Re-checks every real attempt; approval is scoped to one material plan."""

    def __init__(
        self,
        provider: _UsageCapture,
        routing_service: _RoutingContextSource,
        adapter: ExecutionAdapter,
        planner: ExecutionPlanner,
        policy: ExecutionPolicy,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._provider = provider
        self._routing: _RoutingContextSource = routing_service
        self._adapter = adapter
        self._planner = planner
        self._policy = policy
        self._gate = ExecutionPolicyGate(policy)
        self._escalation = EscalationEvaluator(policy)
        self._clock = clock or (lambda: datetime.now(UTC))

    async def create_plan(
        self,
        task: str,
        *,
        working_directory: Path,
        dry_run: bool,
        overrides: TaskProfileOverrides | None = None,
    ) -> ExecutionPlan:
        now = self._clock()
        context = await self._routing.recommend_latest_context(
            task,
            now=now,
            overrides=overrides,
            provider=self._adapter.provider,
        )
        if context is None:
            if dry_run:
                raise NoExecutionSnapshotError(
                    "dry-run requires a persisted snapshot; capture one first"
                )
            context = await self._capture_context(task, overrides=overrides)
            now = self._clock()

        if self._budget_needs_refresh(context):
            if dry_run:
                raise StaleExecutionBudgetError(
                    "dry-run budget is stale; capture a fresh snapshot first"
                )
            context = await self._capture_context(task, overrides=overrides)
            now = self._clock()

        resolved = working_directory.resolve(strict=True)
        preview = self._adapter.command_preview(
            context.recommendation.selected_model_id,
            context.recommendation.selected_effort,
            resolved,
        )
        return await asyncio.to_thread(
            self._planner.build,
            context.recommendation,
            context.budget_report,
            provider=context.provider,
            task_payload=task,
            working_directory=resolved,
            dry_run=dry_run,
            adapter_name=self._adapter.name,
            command_preview=preview,
            planned_at=now,
        )

    async def run_plan(
        self,
        plan: ExecutionPlan,
        *,
        approval_handler: ApprovalHandler | None = None,
        plan_change_handler: ApprovalHandler | None = None,
    ) -> ExecutionResult:
        now = self._clock()
        self._planner.validate_initial(plan)
        if plan.dry_run:
            return self._not_started(
                plan,
                ExecutionStatus.DRY_RUN,
                now,
                message="dry-run completed without invoking an adapter",
            )
        if plan.provider != self._adapter.provider or plan.adapter_name != self._adapter.name:
            raise ExecutionAdapterError("execution plan does not match the configured adapter")
        expected_preview = self._adapter.command_preview(
            plan.model_id,
            plan.effort,
            plan.working_directory,
        )
        if plan.command_preview != expected_preview:
            raise ExecutionAdapterError("execution plan command preview does not match adapter")

        current = plan
        total_attempts = 0
        same_step_retries = 0
        retry_count = 0
        escalation_count = 0
        events = [execution_event(plan, ExecutionStatus.PLANNED, plan.planned_at)]
        approval_reusable = False

        while total_attempts < self._policy.max_attempts:
            decision = self._gate.decide(
                current.task_profile,
                dry_run=False,
                is_escalation=current.escalation_index > 0,
            )
            if not decision.allowed:
                return self._not_started(
                    current,
                    ExecutionStatus.DENIED,
                    self._clock(),
                    message=decision.reason,
                    events=tuple(events),
                    attempt_count=total_attempts,
                    retry_count=retry_count,
                    escalation_count=escalation_count,
                )
            # Interactive clients may require a new UI confirmation for every
            # changed escalation plan even when the core policy permits auto-approval.
            needs_approval = decision.requires_confirmation or (
                current.escalation_index > 0 and plan_change_handler is not None
            )
            if needs_approval and not approval_reusable:
                events.append(
                    execution_event(
                        current,
                        ExecutionStatus.AWAITING_APPROVAL,
                        self._clock(),
                        decision.reason,
                    )
                )
                handler = (
                    approval_handler if decision.requires_confirmation else plan_change_handler
                )
                if handler is None:
                    return self._not_started(
                        current,
                        ExecutionStatus.AWAITING_APPROVAL,
                        self._clock(),
                        message="explicit approval is required",
                        events=tuple(events),
                        attempt_count=total_attempts,
                        retry_count=retry_count,
                        escalation_count=escalation_count,
                    )
                if not await handler(current):
                    return self._not_started(
                        current,
                        ExecutionStatus.DENIED,
                        self._clock(),
                        message="execution was not approved",
                        events=tuple(events),
                        attempt_count=total_attempts,
                        retry_count=retry_count,
                        escalation_count=escalation_count,
                    )
                approval_reusable = True

            revalidated = await self._revalidate(current)
            if isinstance(revalidated, ExecutionResult):
                return revalidated.model_copy(
                    update={
                        "attempt_count": total_attempts,
                        "retry_count": retry_count,
                        "escalation_count": escalation_count,
                        "events": tuple(events) + revalidated.events,
                    }
                )

            raw_result = await self._adapter.execute(current)
            if not isinstance(raw_result, ExecutionResult):
                return self._not_started(
                    current,
                    ExecutionStatus.FAILED,
                    self._clock(),
                    failure_class=FailureClass.VALIDATION,
                    message="execution adapter returned an invalid result",
                    events=tuple(events),
                    attempt_count=total_attempts,
                    retry_count=retry_count,
                    escalation_count=escalation_count,
                )
            if (
                raw_result.execution_id != current.execution_id
                or raw_result.model_id != current.model_id
                or raw_result.effort != current.effort
                or raw_result.task_hash != current.task_hash
            ):
                return self._not_started(
                    current,
                    ExecutionStatus.FAILED,
                    self._clock(),
                    failure_class=FailureClass.VALIDATION,
                    message="execution adapter result does not match its plan",
                    events=tuple(events),
                    attempt_count=total_attempts,
                    retry_count=retry_count,
                    escalation_count=escalation_count,
                )

            total_attempts += 1
            events.extend(raw_result.events)
            if raw_result.status in {
                ExecutionStatus.SUCCEEDED,
                ExecutionStatus.CANCELLED,
            }:
                return raw_result.model_copy(
                    update={
                        "attempt_count": total_attempts,
                        "retry_count": retry_count,
                        "escalation_count": escalation_count,
                        "events": tuple(events),
                    }
                )

            next_action = self._escalation.decide(
                current,
                raw_result,
                total_attempts=total_attempts,
                same_step_retries=same_step_retries,
            )
            if next_action.action is NextAction.RETRY:
                retry_count += 1
                same_step_retries += 1
                events.append(
                    execution_event(
                        current,
                        ExecutionStatus.RETRYING,
                        self._clock(),
                        next_action.reason,
                    )
                )
                current = self._planner.retry(current)
                approval_reusable = True
                continue

            if next_action.action is NextAction.ESCALATE:
                step = current.escalation_path[current.escalation_index]
                escalation_count += 1
                events.append(
                    execution_event(
                        current,
                        ExecutionStatus.ESCALATION_PLANNED,
                        self._clock(),
                        f"next={step.model_id}/{step.effort or 'default'}",
                    )
                )
                current = self._planner.escalate(
                    current,
                    step,
                    revalidated.context.budget_report,
                    command_preview=self._adapter.command_preview(
                        step.model_id,
                        step.effort,
                        current.working_directory,
                    ),
                    planned_at=self._clock(),
                )
                same_step_retries = 0
                approval_reusable = False
                continue

            next_step = self._next_step(current)
            return raw_result.model_copy(
                update={
                    "attempt_count": total_attempts,
                    "retry_count": retry_count,
                    "escalation_count": escalation_count,
                    "events": tuple(events),
                    "escalation_recommended": (
                        next_step is not None
                        and raw_result.failure_class in self._policy.escalation_failures
                    ),
                    "next_step": next_step,
                }
            )

        return self._not_started(
            current,
            ExecutionStatus.FAILED,
            self._clock(),
            failure_class=FailureClass.UNKNOWN,
            message="maximum attempts reached",
            events=tuple(events),
            attempt_count=total_attempts,
            retry_count=retry_count,
            escalation_count=escalation_count,
        )

    async def _capture_context(
        self,
        task: str,
        *,
        overrides: TaskProfileOverrides | None,
        profile: TaskProfile | None = None,
    ) -> RoutingContext:
        snapshot = await self._provider.capture_usage()
        if profile is not None:
            return await asyncio.to_thread(
                self._routing.recommend_profile_snapshot,
                snapshot,
                profile,
                now=self._clock(),
            )
        return await asyncio.to_thread(
            self._routing.recommend_snapshot,
            snapshot,
            task,
            now=self._clock(),
            overrides=overrides,
        )

    def _budget_needs_refresh(self, context: RoutingContext) -> bool:
        age = context.budget_report.snapshot_age_seconds
        return self._policy.require_fresh_budget and (
            age < 0 or age > self._policy.max_budget_age_seconds
        )

    async def _revalidate(
        self,
        plan: ExecutionPlan,
    ) -> _Revalidated | ExecutionResult:
        try:
            context = await self._capture_context(
                plan.task_payload,
                overrides=None,
                profile=plan.task_profile,
            )
        except (CapabilityProfileError, RoutingError):
            return self._changed(
                plan,
                ExecutionStatus.CAPABILITY_CHANGED,
                FailureClass.VALIDATION,
                "current capabilities are no longer routable; rebuild the plan",
            )
        if context.provider != plan.provider:
            return self._changed(
                plan,
                ExecutionStatus.CAPABILITY_CHANGED,
                FailureClass.VALIDATION,
                "provider changed during execution revalidation",
            )
        if self._budget_needs_refresh(context):
            return self._changed(
                plan,
                ExecutionStatus.QUOTA_CHANGED,
                FailureClass.QUOTA,
                "fresh provider capture did not satisfy budget freshness policy",
            )
        if self._quota_changed(plan, context):
            return self._changed(
                plan,
                ExecutionStatus.QUOTA_CHANGED,
                FailureClass.QUOTA,
                "quota context changed materially; re-plan and approve again",
            )

        models = {model.id: model for model in context.capabilities.models}
        selected = models.get(plan.model_id)
        if (
            selected is None
            or not selected.selectable
            or selected.relative_power is None
            or selected.provider != plan.provider
            or (plan.effort is not None and plan.effort not in selected.supported_efforts)
        ):
            return self._changed(
                plan,
                ExecutionStatus.CAPABILITY_CHANGED,
                FailureClass.VALIDATION,
                "planned model or effort is no longer routable",
            )

        recommendation = context.recommendation
        if (
            recommendation.selected_model_id != plan.initial_model_id
            or recommendation.selected_effort != plan.initial_effort
        ):
            return self._changed(
                plan,
                ExecutionStatus.CAPABILITY_CHANGED,
                FailureClass.VALIDATION,
                "routing recommendation changed; rebuild the plan",
            )
        if plan.escalation_index > 0:
            path_index = plan.escalation_index - 1
            if path_index >= len(recommendation.escalation_path):
                return self._changed(
                    plan,
                    ExecutionStatus.CAPABILITY_CHANGED,
                    FailureClass.VALIDATION,
                    "planned escalation step no longer exists",
                )
            live_step = recommendation.escalation_path[path_index]
            if live_step.model_id != plan.model_id or live_step.effort != plan.effort:
                return self._changed(
                    plan,
                    ExecutionStatus.CAPABILITY_CHANGED,
                    FailureClass.VALIDATION,
                    "planned escalation step changed; rebuild the plan",
                )
        return _Revalidated(context)

    def _quota_changed(self, plan: ExecutionPlan, context: RoutingContext) -> bool:
        current = context.budget_report.effective_pressure
        planned = plan.budget_pressure
        if (current is None) != (planned is None):
            return True
        if (
            current is not None
            and planned is not None
            and abs(current - planned) > self._policy.quota_change_threshold
        ):
            return True
        return context.budget_report.binding_pool_id != plan.binding_pool_id

    def _changed(
        self,
        plan: ExecutionPlan,
        status: ExecutionStatus,
        failure_class: FailureClass,
        message: str,
    ) -> ExecutionResult:
        return self._not_started(
            plan,
            status,
            self._clock(),
            failure_class=failure_class,
            message=message,
        )

    @staticmethod
    def _next_step(plan: ExecutionPlan) -> RoutingStep | None:
        if plan.escalation_index >= len(plan.escalation_path):
            return None
        return plan.escalation_path[plan.escalation_index]

    @staticmethod
    def _not_started(
        plan: ExecutionPlan,
        status: ExecutionStatus,
        now: datetime,
        *,
        failure_class: FailureClass | None = None,
        message: str,
        events: tuple[ExecutionEvent, ...] = (),
        attempt_count: int = 0,
        retry_count: int = 0,
        escalation_count: int = 0,
    ) -> ExecutionResult:
        final_events = events + (execution_event(plan, status, now, message),)
        return ExecutionResult(
            execution_id=plan.execution_id,
            task_hash=plan.task_hash,
            started_at=now,
            finished_at=now,
            model_id=plan.model_id,
            effort=plan.effort,
            status=status,
            failure_class=failure_class,
            attempt_count=attempt_count,
            retry_count=retry_count,
            escalation_count=escalation_count,
            events=final_events,
            message=message,
        )
