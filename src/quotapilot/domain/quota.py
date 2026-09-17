"""QuotaPool and QuotaBinding: provider-independent quota representation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

QuotaKind = Literal["rolling", "fixed", "credit", "unknown"]
QuotaScope = Literal["account", "product", "model", "model_group", "unknown"]
BindingConfidence = Literal["provider", "observed", "fallback", "unknown"]


class QuotaPool(BaseModel):
    """A single quota/rate-limit window as reported (or inferred) from a provider.

    Fractions are normalized to 0.0-1.0 when the provider exposes enough
    information to compute them; otherwise they are left as `None` rather
    than guessed.

    `kind`/`scope` reflect QuotaPilot's *current confidence*, not
    necessarily provider-confirmed truth — use `"unknown"` rather than
    guessing when the underlying semantics were not actually confirmed by
    the provider. When a value here is inferred rather than provider-stated,
    the reasoning/evidence belongs in `metadata["provenance"]` under the
    responsible adapter's documented convention. `metadata` is only
    shallowly immutable — see `AIModel`'s docstring for the caveat.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    provider: str

    kind: QuotaKind
    scope: QuotaScope

    used_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    remaining_fraction: float | None = Field(default=None, ge=0.0, le=1.0)

    starts_at: AwareDatetime | None = None
    resets_at: AwareDatetime | None = None
    window_seconds: int | None = Field(default=None, ge=0)

    applies_to_models: tuple[str, ...] = Field(default_factory=tuple)

    raw_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuotaBinding(BaseModel):
    """A many-to-many link between a model (+ optional effort) and quota pools.

    Never assume a single model maps to a single quota pool.

    `confidence` must reflect how the binding was actually established, not
    merely whether a provider *field* was involved in deriving it: a
    binding QuotaPilot constructed from provider data (e.g. by grouping
    provider-reported model/pool associations) is `"observed"`, not
    `"provider"` — reserve `"provider"` for a case where the provider
    itself declares the complete binding (model, pools, and their
    relationship) as a first-class fact. `metadata` should record the
    provenance/evidence used.
    """

    model_config = ConfigDict(frozen=True)

    model_id: str
    reasoning_effort: str | None = None
    quota_pool_ids: tuple[str, ...]

    confidence: BindingConfidence
    metadata: dict[str, Any] = Field(default_factory=dict)
