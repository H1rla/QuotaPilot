"""Strict, versioned models for reviewable routing capability profiles."""

from __future__ import annotations

from datetime import date, timedelta
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SUPPORTED_PROFILE_SCHEMA_VERSION = 1


class ProvenanceSource(StrEnum):
    PROVIDER = "provider"
    BENCHMARK = "benchmark"
    EMPIRICAL = "empirical"
    MANUAL = "manual"
    FALLBACK = "fallback"
    UNKNOWN = "unknown"


class ProvenanceConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    PROVISIONAL = "provisional"


class ProfileFreshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class MetricProvenance(BaseModel):
    """Human-reviewable evidence for every value in one profile entry."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: ProvenanceSource
    confidence: ProvenanceConfidence
    evidence: tuple[str, ...]

    @field_validator("evidence")
    @classmethod
    def evidence_must_be_human_readable(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or any(not item.strip() for item in value):
            raise ValueError("provenance evidence must contain non-blank text")
        return value


class ModelProfile(BaseModel):
    """Optional routing fields for one exact model ID."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    relative_power: float | None = Field(
        default=None, strict=True, ge=0.0, le=1.0, allow_inf_nan=False
    )
    relative_cost: float | None = Field(
        default=None, strict=True, ge=0.0, le=1.0, allow_inf_nan=False
    )
    relative_latency: float | None = Field(
        default=None, strict=True, ge=0.0, le=1.0, allow_inf_nan=False
    )
    effort_order: tuple[str, ...] | None = None
    provenance: MetricProvenance

    @field_validator("effort_order")
    @classmethod
    def effort_order_must_be_explicit_and_unique(
        cls, value: tuple[str, ...] | None
    ) -> tuple[str, ...] | None:
        if value is None:
            return None
        if not value or any(not effort.strip() for effort in value):
            raise ValueError("effort_order must contain non-blank effort names")
        if len(value) != len(set(value)):
            raise ValueError("effort_order must not contain duplicates")
        return value

    @model_validator(mode="after")
    def at_least_one_routing_value(self) -> Self:
        if all(
            value is None
            for value in (
                self.relative_power,
                self.relative_cost,
                self.relative_latency,
                self.effort_order,
            )
        ):
            raise ValueError("a model profile must define at least one routing value")
        return self


class ModelProfileDocument(BaseModel):
    """One versioned provider/product profile file."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(strict=True)
    provider: str = Field(min_length=1)
    product: str = Field(min_length=1)
    verified_at: date
    expires_after_days: int | None = Field(default=None, strict=True, gt=0)
    models: dict[str, ModelProfile]

    @field_validator("schema_version")
    @classmethod
    def schema_version_is_supported(cls, value: int) -> int:
        if value != SUPPORTED_PROFILE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported profile schema version {value}; "
                f"expected {SUPPORTED_PROFILE_SCHEMA_VERSION}"
            )
        return value

    @field_validator("provider", "product")
    @classmethod
    def identity_is_trimmed(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("profile identity fields must not contain outer whitespace")
        return value

    @field_validator("models")
    @classmethod
    def model_ids_are_exact_and_nonempty(
        cls, value: dict[str, ModelProfile]
    ) -> dict[str, ModelProfile]:
        if not value:
            raise ValueError("profile must contain at least one model")
        if any(not model_id or model_id != model_id.strip() for model_id in value):
            raise ValueError("model IDs must be non-blank exact strings")
        return value

    def freshness(self, evaluated_on: date) -> ProfileFreshness:
        if evaluated_on < self.verified_at or self.expires_after_days is None:
            return ProfileFreshness.UNKNOWN
        expires_on = self.verified_at + timedelta(days=self.expires_after_days)
        if evaluated_on > expires_on:
            return ProfileFreshness.STALE
        return ProfileFreshness.FRESH


class ProfileMatch(BaseModel):
    """One exact model match plus document-level freshness context."""

    model_config = ConfigDict(frozen=True)

    provider: str
    product: str
    model_id: str
    schema_version: int
    verified_at: date
    expires_after_days: int | None
    freshness: ProfileFreshness
    profile: ModelProfile
    profile_name: str


class ModelCapabilityView(BaseModel):
    """Privacy-safe observability row for `quotapilot models`."""

    model_config = ConfigDict(frozen=True)

    model_id: str
    provider: str
    selectable: bool
    routable: bool
    relative_power: float | None
    relative_cost: float | None
    relative_latency: float | None
    effort_order: tuple[str, ...] | None
    field_sources: dict[str, str] = Field(default_factory=dict)
    profile_name: str | None = None
    profile_source: ProvenanceSource | None = None
    profile_confidence: ProvenanceConfidence | None = None
    profile_evidence: tuple[str, ...] = Field(default_factory=tuple)
    verified_at: date | None = None
    freshness: ProfileFreshness | None = None
    warnings: tuple[str, ...] = Field(default_factory=tuple)
