"""Provider-neutral models for deterministic advisory routing."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TaskClass(StrEnum):
    MECHANICAL = "mechanical"
    LOCAL_IMPLEMENTATION = "local_implementation"
    DEBUGGING = "debugging"
    REPOSITORY_CHANGE = "repository_change"
    ARCHITECTURE = "architecture"
    RESEARCH = "research"
    REVIEW = "review"
    UNKNOWN = "unknown"


class ProfileSource(StrEnum):
    HEURISTIC = "heuristic"
    EXPLICIT = "explicit"
    MIXED = "mixed"


class QuotaPressureSource(StrEnum):
    BUDGET_REPORT = "budget_report"
    FALLBACK_UNKNOWN = "fallback_unknown"


class MetadataSource(StrEnum):
    CAPABILITY = "capability"
    FALLBACK_NEUTRAL = "fallback_neutral"


class RecommendationConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskProfile(BaseModel):
    """Normalized task characteristics; values are policy inputs, not facts."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    summary: str = Field(min_length=1)
    complexity: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    ambiguity: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    failure_cost: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    verifiability: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    context_demand: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    latency_sensitivity: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    task_class: TaskClass
    tags: tuple[str, ...] = Field(default_factory=tuple)
    profile_source: ProfileSource

    @field_validator("summary")
    @classmethod
    def summary_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("task summary must not be blank")
        return value


class TaskProfileOverrides(BaseModel):
    """Optional explicit values layered over deterministic heuristics."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    complexity: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    ambiguity: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    failure_cost: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    verifiability: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    context_demand: float | None = Field(default=None, ge=0.0, le=1.0, allow_inf_nan=False)
    latency_sensitivity: float | None = Field(
        default=None, ge=0.0, le=1.0, allow_inf_nan=False
    )
    task_class: TaskClass | None = None


class RoutingPolicy(BaseModel):
    """Strict, provider-independent scoring and escalation policy."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    quota_pressure_weight: float = Field(default=0.35, ge=0.0, allow_inf_nan=False)
    latency_weight: float = Field(default=0.20, ge=0.0, allow_inf_nan=False)
    overcapability_weight: float = Field(default=0.15, ge=0.0, allow_inf_nan=False)
    required_failure_weight: float = Field(default=0.10, ge=0.0, allow_inf_nan=False)
    required_low_verifiability_weight: float = Field(
        default=0.10, ge=0.0, allow_inf_nan=False
    )
    underpower_tolerance: float = Field(default=0.15, ge=0.0, le=1.0)
    risk_tolerance_reduction: float = Field(default=0.10, ge=0.0, le=1.0)
    unknown_quota_pressure: float = Field(default=0.50, ge=0.0, le=1.0)
    missing_cost_fallback: float = Field(default=0.50, ge=0.0, le=1.0)
    missing_latency_fallback: float = Field(default=0.50, ge=0.0, le=1.0)
    effort_quota_reduction: float = Field(default=0.25, ge=0.0, le=1.0)
    escalation_enabled: bool = True
    max_escalation_steps: int = Field(default=3, ge=0, le=10)
    max_alternatives: int = Field(default=3, ge=0, le=10)

    @model_validator(mode="after")
    def tolerance_reduction_is_bounded(self) -> Self:
        if self.risk_tolerance_reduction > self.underpower_tolerance:
            raise ValueError("risk_tolerance_reduction cannot exceed underpower_tolerance")
        return self


class CandidateScore(BaseModel):
    """Inspectable score components for one discovered model."""

    model_config = ConfigDict(frozen=True)

    model_id: str
    selectable: bool
    relative_power: float | None = Field(default=None, ge=0.0, le=1.0)
    relative_cost: float | None = Field(default=None, ge=0.0, le=1.0)
    relative_latency: float | None = Field(default=None, ge=0.0, le=1.0)
    effective_cost: float | None = Field(default=None, ge=0.0, le=1.0)
    effective_latency: float | None = Field(default=None, ge=0.0, le=1.0)
    cost_source: MetadataSource | None = None
    latency_source: MetadataSource | None = None
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    quota_penalty: float | None = Field(default=None, ge=0.0)
    latency_penalty: float | None = Field(default=None, ge=0.0)
    overcapability_penalty: float | None = Field(default=None, ge=0.0)
    utility: float | None = None
    eligible: bool
    rejection_reason: str | None = None


class RoutingStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_id: str
    effort: str | None
    reason: str


class RoutingRecommendation(BaseModel):
    """Complete advisory result; it never authorizes or performs execution."""

    model_config = ConfigDict(frozen=True)

    task_profile: TaskProfile
    difficulty_score: float = Field(ge=0.0, le=1.0)
    required_power: float = Field(ge=0.0, le=1.0)
    capability_floor: float = Field(ge=0.0, le=1.0)
    effort_demand: float = Field(ge=0.0, le=1.0)

    quota_pressure: float = Field(ge=0.0, le=1.0)
    quota_pressure_source: QuotaPressureSource
    binding_pool_id: str | None = None

    selected_model_id: str
    selected_effort: str | None
    candidate_scores: tuple[CandidateScore, ...]
    escalation_path: tuple[RoutingStep, ...]
    alternatives: tuple[RoutingStep, ...]
    explanation: tuple[str, ...]
    warnings: tuple[str, ...]
    confidence: RecommendationConfidence
