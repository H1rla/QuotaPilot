"""Central strict configuration composed from existing policy models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from quotapilot.budget.models import BudgetConfig
from quotapilot.execution.models import ExecutionPolicy
from quotapilot.routing.models import RoutingPolicy


class ProviderConfig(BaseModel):
    """Provider selection for persisted-state commands."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    default: str | None = None

    @field_validator("default")
    @classmethod
    def default_provider_is_not_blank(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or value != value.strip()):
            raise ValueError("default provider must be a non-blank trimmed string")
        return value


class DatabaseConfig(BaseModel):
    """Optional local database override; platformdirs remains the default."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    path: str | None = None

    @field_validator("path")
    @classmethod
    def path_is_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("database path must not be blank")
        return value


class ProfilesConfig(BaseModel):
    """Optional local profile directory; bundled profiles are the default."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    directory: str | None = None

    @field_validator("directory")
    @classmethod
    def directory_is_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("profile directory must not be blank")
        return value


class LanguagePreference(StrEnum):
    """Supported GUI language selection modes."""

    SYSTEM = "system"
    ENGLISH = "en"
    JAPANESE = "ja"


class AppearanceConfig(BaseModel):
    """Presentation preferences that are safe to apply independently."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    language: LanguagePreference = LanguagePreference.SYSTEM


class AppConfig(BaseModel):
    """Effective application policy with no duplicated policy definitions."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    routing: RoutingPolicy = Field(default_factory=RoutingPolicy)
    execution: ExecutionPolicy = Field(default_factory=ExecutionPolicy)
    profiles: ProfilesConfig = Field(default_factory=ProfilesConfig)
    appearance: AppearanceConfig = Field(default_factory=AppearanceConfig)
