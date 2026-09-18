"""Strict machine-facing models for product observability surfaces."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from quotapilot.budget.models import BudgetState
from quotapilot.capabilities.models import ProfileFreshness


class SnapshotSource(StrEnum):
    LIVE_CAPTURE = "live_capture"
    PERSISTED = "persisted"
    PERSISTED_FALLBACK = "persisted_fallback"


class ProfileStatus(BaseModel):
    """Aggregated, account-private capability-profile health."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    evaluated_on: date
    freshness: ProfileFreshness
    model_count: int = Field(ge=0)
    routable_model_count: int = Field(ge=0)
    profiled_model_count: int = Field(ge=0)


class StatusPool(BaseModel):
    """Privacy-safe quota pool status derived from a BudgetReport."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    pool_id: str
    name: str | None = None
    state: BudgetState
    used_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    remaining_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    today_budget_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    resets_at: AwareDatetime | None = None
    warnings: tuple[str, ...] = Field(default_factory=tuple)


class StatusReport(BaseModel):
    """Stable operational overview with no account identity or raw observation."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    schema_version: int = 1
    provider: str
    product: str | None = None
    source: SnapshotSource
    captured_at: AwareDatetime
    evaluated_at: AwareDatetime
    snapshot_age_seconds: float
    is_stale: bool
    pools: tuple[StatusPool, ...]
    effective_pressure: float | None = Field(default=None, ge=0.0, le=1.0)
    binding_pool_id: str | None = None
    profile: ProfileStatus
    warnings: tuple[str, ...] = Field(default_factory=tuple)


class WaybarPayload(BaseModel):
    """Waybar custom-module JSON contract."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    text: str
    tooltip: str
    class_name: str = Field(serialization_alias="class")
