"""Provider-neutral policy and report models for quota budgeting."""

from __future__ import annotations

from enum import StrEnum
from itertools import pairwise
from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class BudgetState(StrEnum):
    VERY_UNDER = "very_under"
    UNDER = "under"
    ON_TRACK = "on_track"
    OVER = "over"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class TimingSource(StrEnum):
    START_RESET = "start_reset"
    DERIVED_WINDOW_SECONDS = "derived_window_seconds"


class RemainingSource(StrEnum):
    REPORTED = "reported"
    DERIVED_USED_FRACTION = "derived_used_fraction"


class WeekdayWeights(BaseModel):
    """Non-negative calendar-day allocation weights, Monday first."""

    model_config = ConfigDict(frozen=True)

    monday: float = Field(default=1.0, ge=0.0, allow_inf_nan=False)
    tuesday: float = Field(default=1.0, ge=0.0, allow_inf_nan=False)
    wednesday: float = Field(default=1.0, ge=0.0, allow_inf_nan=False)
    thursday: float = Field(default=1.0, ge=0.0, allow_inf_nan=False)
    friday: float = Field(default=1.0, ge=0.0, allow_inf_nan=False)
    saturday: float = Field(default=1.0, ge=0.0, allow_inf_nan=False)
    sunday: float = Field(default=1.0, ge=0.0, allow_inf_nan=False)

    @model_validator(mode="after")
    def at_least_one_positive_weight(self) -> Self:
        if not any(weight > 0.0 for weight in self.as_tuple()):
            raise ValueError("at least one weekday weight must be positive")
        return self

    def as_tuple(self) -> tuple[float, ...]:
        return (
            self.monday,
            self.tuesday,
            self.wednesday,
            self.thursday,
            self.friday,
            self.saturday,
            self.sunday,
        )

    def for_weekday(self, weekday: int) -> float:
        return self.as_tuple()[weekday]


class BudgetConfig(BaseModel):
    """Quota policy only; contains no provider or plan-specific settings."""

    model_config = ConfigDict(frozen=True)

    reserve_fraction: float = Field(default=0.10, ge=0.0, lt=1.0, allow_inf_nan=False)

    very_under_threshold: float = Field(default=-0.20, allow_inf_nan=False)
    under_threshold: float = Field(default=-0.07, allow_inf_nan=False)
    over_threshold: float = Field(default=0.07, allow_inf_nan=False)
    critical_threshold: float = Field(default=0.20, allow_inf_nan=False)

    very_under_pressure: float = Field(
        default=0.00, ge=0.0, le=1.0, allow_inf_nan=False
    )
    under_pressure: float = Field(default=0.15, ge=0.0, le=1.0, allow_inf_nan=False)
    on_track_pressure: float = Field(
        default=0.35, ge=0.0, le=1.0, allow_inf_nan=False
    )
    over_pressure: float = Field(default=0.70, ge=0.0, le=1.0, allow_inf_nan=False)
    critical_pressure: float = Field(default=1.00, ge=0.0, le=1.0, allow_inf_nan=False)

    weekday_weights: WeekdayWeights = Field(default_factory=WeekdayWeights)
    timezone: str = "UTC"
    stale_after_seconds: int = Field(default=900, gt=0)

    @field_validator("timezone")
    @classmethod
    def timezone_must_exist(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown IANA timezone: {value}") from exc
        return value

    @model_validator(mode="after")
    def policy_ordering_is_valid(self) -> Self:
        thresholds = (
            self.very_under_threshold,
            self.under_threshold,
            self.over_threshold,
            self.critical_threshold,
        )
        if any(left >= right for left, right in pairwise(thresholds)):
            raise ValueError("budget state thresholds must be strictly increasing")

        pressures = (
            self.very_under_pressure,
            self.under_pressure,
            self.on_track_pressure,
            self.over_pressure,
            self.critical_pressure,
        )
        if any(left > right for left, right in pairwise(pressures)):
            raise ValueError("budget pressures must be non-decreasing")
        return self


class PoolBudgetAssessment(BaseModel):
    """One quota pool's provider-neutral, reserve-aware budget state."""

    model_config = ConfigDict(frozen=True)

    pool_id: str
    pool_name: str | None = None
    resets_at: AwareDatetime | None = None

    actual_usage: float | None = Field(default=None, ge=0.0, le=1.0)
    expected_usage: float | None = Field(default=None, ge=0.0, le=1.0)
    pace_delta: float | None = Field(default=None, ge=-1.0, le=1.0)

    remaining_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    remaining_source: RemainingSource | None = None
    available_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    today_budget_fraction: float | None = Field(default=None, ge=0.0, le=1.0)

    window_progress: float | None = Field(default=None, ge=0.0, le=1.0)
    time_until_reset_seconds: int | None = Field(default=None, ge=0)

    state: BudgetState
    pressure: float | None = Field(default=None, ge=0.0, le=1.0)
    timing_source: TimingSource | None = None
    warnings: tuple[str, ...] = Field(default_factory=tuple)


class BudgetReport(BaseModel):
    """Deterministic snapshot-level result; intentionally contains no account ID."""

    model_config = ConfigDict(frozen=True)

    captured_at: AwareDatetime
    evaluated_at: AwareDatetime
    snapshot_age_seconds: float
    is_stale: bool
    reserve_fraction: float = Field(ge=0.0, lt=1.0)
    timezone: str

    pools: tuple[PoolBudgetAssessment, ...]
    effective_pressure: float | None = Field(default=None, ge=0.0, le=1.0)
    binding_pool_id: str | None = None
    warnings: tuple[str, ...] = Field(default_factory=tuple)
