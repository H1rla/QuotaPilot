"""Strict provider-neutral models for controlled external-agent execution."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from quotapilot.routing.models import RoutingStep, TaskClass, TaskProfile


class ExecutionStatus(StrEnum):
    PLANNED = "planned"
    DRY_RUN = "dry_run"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    RETRYING = "retrying"
    ESCALATION_PLANNED = "escalation_planned"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DENIED = "denied"
    QUOTA_CHANGED = "quota_changed"
    CAPABILITY_CHANGED = "capability_changed"


class FailureClass(StrEnum):
    TRANSPORT = "transport"
    AUTHENTICATION = "authentication"
    QUOTA = "quota"
    TIMEOUT = "timeout"
    AGENT_ERROR = "agent_error"
    VALIDATION = "validation"
    EXECUTION_ENVIRONMENT = "execution_environment"
    USER_CANCELLED = "user_cancelled"
    UNKNOWN = "unknown"


class ExecutionMode(StrEnum):
    NEVER_EXECUTE = "never_execute"
    ALWAYS_CONFIRM = "always_confirm"
    CONFIRM_ON_ESCALATION = "confirm_on_escalation"
    AUTO_FOR_LOW_RISK = "auto_for_low_risk"


class ExecutionPolicy(BaseModel):
    """Strict bounded-execution policy; routing policy remains separate."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    mode: ExecutionMode = ExecutionMode.ALWAYS_CONFIRM
    max_attempts: int = Field(default=3, ge=1, le=10)
    max_same_step_retries: int = Field(default=1, ge=0, le=5)
    timeout_seconds: int = Field(default=900, ge=1, le=86_400)
    max_output_bytes: int = Field(default=32_768, ge=1_024, le=1_048_576)
    require_fresh_budget: bool = True
    max_budget_age_seconds: int = Field(default=300, ge=1)
    quota_change_threshold: float = Field(
        default=0.10, ge=0.0, le=1.0, allow_inf_nan=False
    )
    allow_escalation: bool = True

    low_risk_max_complexity: float = Field(
        default=0.35, ge=0.0, le=1.0, allow_inf_nan=False
    )
    low_risk_max_ambiguity: float = Field(
        default=0.25, ge=0.0, le=1.0, allow_inf_nan=False
    )
    low_risk_max_failure_cost: float = Field(
        default=0.25, ge=0.0, le=1.0, allow_inf_nan=False
    )
    low_risk_min_verifiability: float = Field(
        default=0.75, ge=0.0, le=1.0, allow_inf_nan=False
    )

    retryable_failures: tuple[FailureClass, ...] = (FailureClass.TRANSPORT,)
    escalation_failures: tuple[FailureClass, ...] = (
        FailureClass.AGENT_ERROR,
        FailureClass.VALIDATION,
    )

    @model_validator(mode="after")
    def retry_budget_fits_total_attempts(self) -> Self:
        if self.max_same_step_retries >= self.max_attempts:
            raise ValueError("max_same_step_retries must be smaller than max_attempts")
        if len(set(self.retryable_failures)) != len(self.retryable_failures):
            raise ValueError("retryable_failures must not contain duplicates")
        if len(set(self.escalation_failures)) != len(self.escalation_failures):
            raise ValueError("escalation_failures must not contain duplicates")
        forbidden = {
            FailureClass.AUTHENTICATION,
            FailureClass.QUOTA,
            FailureClass.USER_CANCELLED,
            FailureClass.EXECUTION_ENVIRONMENT,
        }
        if forbidden & set(self.retryable_failures):
            raise ValueError("non-retryable failure class configured for retry")
        if forbidden & set(self.escalation_failures):
            raise ValueError("unsafe failure class configured for escalation")
        return self


class ExecutionPlan(BaseModel):
    """Inspectable plan; raw task/profile remain in memory and out of JSON."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    execution_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    effort: str | None = None
    initial_model_id: str = Field(min_length=1)
    initial_effort: str | None = None

    task_payload: str = Field(min_length=1, exclude=True, repr=False)
    task_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    task_profile: TaskProfile = Field(exclude=True, repr=False)
    task_class: TaskClass
    recommendation_link: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    attempt_number: int = Field(ge=1)
    escalation_index: int = Field(default=0, ge=0)
    max_attempts: int = Field(ge=1, le=10)
    dry_run: bool
    requires_confirmation: bool

    working_directory: Path
    timeout_seconds: int = Field(ge=1, le=86_400)
    adapter_name: str = Field(min_length=1)
    command_preview: tuple[str, ...]

    quota_snapshot_captured_at: AwareDatetime
    budget_pressure: float | None = Field(default=None, ge=0.0, le=1.0)
    binding_pool_id: str | None = None
    planned_at: AwareDatetime

    escalation_path: tuple[RoutingStep, ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("task_payload")
    @classmethod
    def task_payload_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("task payload must not be blank")
        return value

    @field_validator("working_directory")
    @classmethod
    def working_directory_is_explicit(cls, value: Path) -> Path:
        if not value.is_absolute() or not value.is_dir():
            raise ValueError("working directory must be an existing absolute directory")
        return value

    @field_validator("command_preview")
    @classmethod
    def command_preview_is_nonempty(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not item for item in value):
            raise ValueError("command preview must contain non-empty arguments")
        return value


class ExecutionEvent(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    status: ExecutionStatus
    occurred_at: AwareDatetime
    attempt_number: int = Field(ge=0)
    model_id: str
    effort: str | None = None
    detail: str | None = None


class ExecutionResult(BaseModel):
    """Bounded execution outcome; never contains the raw task or environment."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    execution_id: str
    task_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    started_at: AwareDatetime
    finished_at: AwareDatetime
    model_id: str
    effort: str | None
    status: ExecutionStatus
    exit_code: int | None = None
    stdout_summary: str | None = None
    stderr_summary: str | None = None
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    failure_class: FailureClass | None = None
    escalation_recommended: bool = False
    next_step: RoutingStep | None = None
    attempt_count: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    escalation_count: int = Field(default=0, ge=0)
    events: tuple[ExecutionEvent, ...] = Field(default_factory=tuple)
    message: str | None = None

    @model_validator(mode="after")
    def timestamps_and_failure_are_coherent(self) -> Self:
        if self.finished_at.astimezone(UTC) < self.started_at.astimezone(UTC):
            raise ValueError("finished_at cannot precede started_at")
        if self.status is ExecutionStatus.SUCCEEDED and self.failure_class is not None:
            raise ValueError("successful execution cannot carry a failure class")
        failure_statuses = {
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.QUOTA_CHANGED,
            ExecutionStatus.CAPABILITY_CHANGED,
        }
        if self.status in failure_statuses and self.failure_class is None:
            raise ValueError("failed execution status requires a failure class")
        return self


def execution_event(
    plan: ExecutionPlan,
    status: ExecutionStatus,
    occurred_at: datetime,
    detail: str | None = None,
) -> ExecutionEvent:
    return ExecutionEvent(
        status=status,
        occurred_at=occurred_at,
        attempt_number=plan.attempt_number,
        model_id=plan.model_id,
        effort=plan.effort,
        detail=detail,
    )
