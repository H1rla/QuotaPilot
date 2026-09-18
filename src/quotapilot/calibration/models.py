"""Provider-independent calibration scenario and result models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from quotapilot.budget.models import BudgetReport, BudgetState
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.model import AIModel
from quotapilot.routing.models import ProfileSource, TaskClass, TaskProfile

CALIBRATION_SCHEMA_VERSION = 1
_EVALUATED_AT = datetime(2026, 9, 18, 12, tzinfo=UTC)
_PRESSURE_BY_STATE = {
    BudgetState.VERY_UNDER: 0.0,
    BudgetState.UNDER: 0.15,
    BudgetState.ON_TRACK: 0.35,
    BudgetState.OVER: 0.70,
    BudgetState.CRITICAL: 1.0,
    BudgetState.UNKNOWN: None,
}


class CalibrationModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str = Field(min_length=1)
    selectable: bool = Field(default=True, strict=True)
    relative_power: float = Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)
    relative_cost: float = Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)
    relative_latency: float = Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)
    effort_order: tuple[str, ...]

    @field_validator("effort_order")
    @classmethod
    def efforts_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or len(value) != len(set(value)):
            raise ValueError("calibration effort_order must be non-empty and unique")
        return value

    def to_domain(self) -> AIModel:
        return AIModel(
            id=self.model_id,
            provider="calibration",
            selectable=self.selectable,
            supported_efforts=self.effort_order,
            effort_order=self.effort_order,
            relative_power=self.relative_power,
            relative_cost=self.relative_cost,
            relative_latency=self.relative_latency,
            metadata={"source": "synthetic_calibration"},
        )


class CalibrationTask(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: str = Field(min_length=1)
    task_class: TaskClass
    complexity: float = Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)
    ambiguity: float = Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)
    failure_cost: float = Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)
    verifiability: float = Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)
    context_demand: float = Field(strict=True, ge=0.0, le=1.0, allow_inf_nan=False)
    latency_sensitivity: float = Field(
        strict=True, ge=0.0, le=1.0, allow_inf_nan=False
    )

    def to_task_profile(self) -> TaskProfile:
        return TaskProfile(
            summary=self.summary,
            task_class=self.task_class,
            complexity=self.complexity,
            ambiguity=self.ambiguity,
            failure_cost=self.failure_cost,
            verifiability=self.verifiability,
            context_demand=self.context_demand,
            latency_sensitivity=self.latency_sensitivity,
            tags=("synthetic-calibration",),
            profile_source=ProfileSource.EXPLICIT,
        )


class CalibrationScenario(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: str = Field(min_length=1)
    capability_profile_version: str = Field(min_length=1)
    task: CalibrationTask
    quota_state: BudgetState
    quota_pressure: float | None = Field(
        default=None, strict=True, ge=0.0, le=1.0, allow_inf_nan=False
    )
    acceptable_models: tuple[str, ...]
    unacceptable_models: tuple[str, ...] = Field(default_factory=tuple)
    anti_waste_guard: bool = Field(default=False, strict=True)
    notes: str = Field(min_length=1)

    @model_validator(mode="after")
    def outcome_and_pressure_are_coherent(self) -> Self:
        if not self.acceptable_models:
            raise ValueError("acceptable_models must not be empty")
        if set(self.acceptable_models) & set(self.unacceptable_models):
            raise ValueError("acceptable and unacceptable model sets must be disjoint")
        if self.quota_pressure != _PRESSURE_BY_STATE[self.quota_state]:
            raise ValueError("quota_pressure must match the declared quota_state")
        return self

    def budget_report(self) -> BudgetReport:
        return BudgetReport(
            captured_at=_EVALUATED_AT,
            evaluated_at=_EVALUATED_AT,
            snapshot_age_seconds=0.0,
            is_stale=False,
            reserve_fraction=0.10,
            timezone="UTC",
            pools=(),
            effective_pressure=self.quota_pressure,
            binding_pool_id=None,
            warnings=(),
        )


class CalibrationSuite(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(strict=True)
    capability_profile_version: str = Field(min_length=1)
    models: tuple[CalibrationModel, ...]
    scenarios: tuple[CalibrationScenario, ...]

    @field_validator("schema_version")
    @classmethod
    def version_is_supported(cls, value: int) -> int:
        if value != CALIBRATION_SCHEMA_VERSION:
            raise ValueError(f"unsupported calibration schema version {value}")
        return value

    @model_validator(mode="after")
    def identities_and_references_are_valid(self) -> Self:
        model_ids = [model.model_id for model in self.models]
        if not model_ids or len(model_ids) != len(set(model_ids)):
            raise ValueError("calibration model IDs must be non-empty and unique")
        scenario_ids = [scenario.scenario_id for scenario in self.scenarios]
        if not scenario_ids or len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("calibration scenario IDs must be non-empty and unique")
        known = set(model_ids)
        for scenario in self.scenarios:
            if scenario.capability_profile_version != self.capability_profile_version:
                raise ValueError("scenario capability profile version does not match suite")
            referenced = set(scenario.acceptable_models) | set(
                scenario.unacceptable_models
            )
            if not referenced <= known:
                raise ValueError("scenario references an unknown calibration model")
        return self

    def capabilities(self) -> CapabilitySet:
        return CapabilitySet(
            models=tuple(model.to_domain() for model in self.models),
            supports_reasoning_effort=True,
            supports_model_selection=True,
            metadata={
                "source": "synthetic_calibration",
                "profile_version": self.capability_profile_version,
            },
        )


class ViolationKind(StrEnum):
    UNACCEPTABLE_RECOMMENDATION = "unacceptable_recommendation"
    CAPABILITY_FLOOR = "capability_floor"
    ANTI_WASTE = "anti_waste"
    UNKNOWN_QUOTA = "unknown_quota"
    UNSUPPORTED_EFFORT = "unsupported_effort"
    NON_SELECTABLE_MODEL = "non_selectable_model"
    DETERMINISM = "determinism"
    NO_RECOMMENDATION = "no_recommendation"


class CalibrationViolation(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_id: str
    kind: ViolationKind
    detail: str


class ScenarioOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_id: str
    selected_model_id: str | None
    selected_effort: str | None
    acceptable_hit: bool
    violations: tuple[CalibrationViolation, ...]


class CalibrationMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    scenario_count: int = Field(ge=0)
    acceptable_hits: int = Field(ge=0)
    unacceptable_recommendations: int = Field(ge=0)
    capability_floor_violations: int = Field(ge=0)
    anti_waste_violations: int = Field(ge=0)
    unknown_quota_violations: int = Field(ge=0)
    unsupported_effort_violations: int = Field(ge=0)
    non_selectable_model_violations: int = Field(ge=0)
    determinism_violations: int = Field(ge=0)
    routing_failures: int = Field(ge=0)


class CalibrationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    capability_profile_version: str
    metrics: CalibrationMetrics
    outcomes: tuple[ScenarioOutcome, ...]
    violations: tuple[CalibrationViolation, ...]
    passed: bool
