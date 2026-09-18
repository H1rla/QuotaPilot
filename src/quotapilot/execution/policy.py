"""Pure execution authorization policy, separate from routing recommendation."""

from __future__ import annotations

from dataclasses import dataclass

from quotapilot.execution.models import ExecutionMode, ExecutionPolicy
from quotapilot.routing.models import TaskProfile


@dataclass(frozen=True, slots=True)
class ExecutionDecision:
    allowed: bool
    requires_confirmation: bool
    reason: str


class ExecutionPolicyGate:
    def __init__(self, policy: ExecutionPolicy) -> None:
        self.policy = policy

    def is_low_risk(self, profile: TaskProfile) -> bool:
        policy = self.policy
        return (
            profile.complexity <= policy.low_risk_max_complexity
            and profile.ambiguity <= policy.low_risk_max_ambiguity
            and profile.failure_cost <= policy.low_risk_max_failure_cost
            and profile.verifiability >= policy.low_risk_min_verifiability
        )

    def decide(
        self,
        profile: TaskProfile,
        *,
        dry_run: bool,
        is_escalation: bool,
    ) -> ExecutionDecision:
        if dry_run:
            return ExecutionDecision(True, False, "dry_run_never_executes")
        if self.policy.mode is ExecutionMode.NEVER_EXECUTE:
            return ExecutionDecision(False, False, "execution_disabled_by_policy")

        low_risk = self.is_low_risk(profile)
        if self.policy.mode is ExecutionMode.ALWAYS_CONFIRM:
            return ExecutionDecision(True, True, "policy_requires_confirmation")
        if not low_risk:
            return ExecutionDecision(True, True, "task_risk_requires_confirmation")
        if self.policy.mode is ExecutionMode.CONFIRM_ON_ESCALATION:
            return ExecutionDecision(
                True,
                is_escalation,
                "escalation_requires_confirmation" if is_escalation else "low_risk_initial_auto",
            )
        return ExecutionDecision(True, is_escalation, "low_risk_auto_execution")
