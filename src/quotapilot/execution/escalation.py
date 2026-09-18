"""Pure bounded retry/escalation decisions over structured failures."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from quotapilot.execution.models import ExecutionPlan, ExecutionPolicy, ExecutionResult


class NextAction(StrEnum):
    STOP = "stop"
    RETRY = "retry"
    ESCALATE = "escalate"


@dataclass(frozen=True, slots=True)
class EscalationDecision:
    action: NextAction
    reason: str


class EscalationEvaluator:
    """Never invents a step; it only permits retry or the next routed step."""

    def __init__(self, policy: ExecutionPolicy) -> None:
        self.policy = policy

    def decide(
        self,
        plan: ExecutionPlan,
        result: ExecutionResult,
        *,
        total_attempts: int,
        same_step_retries: int,
    ) -> EscalationDecision:
        if result.failure_class is None:
            return EscalationDecision(NextAction.STOP, "no_structured_failure")
        if total_attempts >= self.policy.max_attempts:
            return EscalationDecision(NextAction.STOP, "maximum_attempts_reached")
        if result.failure_class in self.policy.retryable_failures:
            if same_step_retries < self.policy.max_same_step_retries:
                return EscalationDecision(NextAction.RETRY, "retryable_failure")
            # A policy may explicitly classify the same failure for escalation
            # after its same-step retry budget has been exhausted.
            if result.failure_class not in self.policy.escalation_failures:
                return EscalationDecision(NextAction.STOP, "same_step_retry_limit_reached")
        if (
            self.policy.allow_escalation
            and result.failure_class in self.policy.escalation_failures
            and plan.escalation_index < len(plan.escalation_path)
        ):
            return EscalationDecision(NextAction.ESCALATE, "structured_failure")
        return EscalationDecision(NextAction.STOP, "failure_not_eligible")
