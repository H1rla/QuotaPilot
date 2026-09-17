"""Typed shapes for `codex app-server` RPC responses (Codex-specific).

These mirror the verified JSON Schema for `account/read`,
`account/rateLimits/read`, and `model/list` (see `docs/DECISIONS.md`), not
the design document's original guesses. Every model uses `extra="allow"`
and leaves provider-controlled enums as plain `str` (never a closed
`Literal`) so that a field or category value we have not seen yet is
preserved rather than rejected — parsing must never crash on an unknown
provider value; only `parser.py`'s conversion into `quotapilot.domain`
types enforces QuotaPilot's own normalized ranges.

This module must not be imported by `quotapilot.domain`, `budget`, or
`routing` — it is provider-internal.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from .errors import CodexNormalizationError


def parse_codex_response[T: "CodexResponseModel"](
    model_cls: type[T], raw: object, *, context: str
) -> T:
    """Validate `raw` against `model_cls`, wrapping failures as `CodexNormalizationError`.

    This is the one place raw Codex JSON should ever be turned into a
    `CodexResponseModel` — every call site (the provider adapter, and
    fixture-driven tests) should go through it so "invalid provider
    response structure" always surfaces as the same typed error rather than
    a bare `pydantic.ValidationError` some callers forget to catch.
    """
    try:
        return model_cls.model_validate(raw)
    except ValidationError as exc:
        raise CodexNormalizationError(f"{context}: invalid provider response structure") from exc


class CodexResponseModel(BaseModel):
    """Base for raw Codex RPC response shapes: tolerant and camelCase-aware."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="allow",
    )


class CodexAccount(CodexResponseModel):
    """The `Account` discriminated union, kept permissive.

    Real variants seen in the verified schema are `apiKey`, `chatgpt`, and
    `amazonBedrock`, but `type` is deliberately `str` (not a closed
    `Literal`) so a future variant does not fail validation. Only
    `chatgpt` accounts carry `email`/`plan_type` in practice.
    """

    type: str
    email: str | None = None
    plan_type: str | None = None
    uses_codex_managed_credentials: bool | None = None


class GetAccountResponse(CodexResponseModel):
    """Response shape for `account/read`."""

    account: CodexAccount | None = None
    requires_openai_auth: bool


class CreditsSnapshot(CodexResponseModel):
    has_credits: bool
    unlimited: bool
    balance: str | None = None


class RateLimitWindow(CodexResponseModel):
    """One usage window. Codex gives no explicit window-start field.

    All numeric fields are strict integers: the verified schema provides no
    alternate string/boolean/float representation, so coercing one would hide
    a malformed provider response. Percent and time values are also bounded
    to their meaningful non-negative domains.
    """

    used_percent: int = Field(strict=True, ge=0, le=100)
    resets_at: int | None = Field(default=None, strict=True, ge=0)
    window_duration_mins: int | None = Field(default=None, strict=True, ge=0)


class RateLimitSnapshot(CodexResponseModel):
    """Usage state for one metered `limit_id` (e.g. `"codex"`)."""

    limit_id: str | None = None
    limit_name: str | None = None
    normal_model_slug: str | None = None
    primary: RateLimitWindow | None = None
    secondary: RateLimitWindow | None = None
    credits: CreditsSnapshot | None = None
    plan_type: str | None = None
    spend_control_reached: bool | None = None
    rate_limit_reached_type: str | None = None


class GetAccountRateLimitsResponse(CodexResponseModel):
    """Response shape for `account/rateLimits/read`."""

    account_id: str | None = None
    ordinary_usage_allowed: bool | None = None
    rate_limits: RateLimitSnapshot
    rate_limits_by_limit_id: dict[str, RateLimitSnapshot] | None = None


class ReasoningEffortOption(CodexResponseModel):
    reasoning_effort: str
    description: str | None = None


class CodexModelEntry(CodexResponseModel):
    """One entry from `model/list`."""

    id: str
    model: str | None = None
    display_name: str | None = None
    hidden: bool = False
    is_default: bool = False
    supported_reasoning_efforts: list[ReasoningEffortOption] = Field(default_factory=list)
    default_reasoning_effort: str | None = None


class ModelListResponse(CodexResponseModel):
    """Response shape for `model/list`."""

    data: list[CodexModelEntry] = Field(default_factory=list)
    next_cursor: str | None = None
