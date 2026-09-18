"""AIModel: a single model exposed by a provider."""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AIModel(BaseModel):
    """A model exposed by a provider, with QuotaPilot routing heuristics.

    `relative_power`, `relative_cost`, and `relative_latency` are QuotaPilot's
    own routing heuristics, not official provider specifications.

    Immutability note: `model_config = frozen=True` makes the top-level
    fields on this model immutable (no reassignment), and `supported_efforts`
    is a `tuple` specifically so it cannot be mutated in place either (e.g.
    `.append(...)`). `metadata` is a plain `dict` and is only *shallowly*
    immutable — the model instance can't be told to point at a different
    dict, but the dict's contents are not deep-frozen. Callers must treat
    `metadata` as read-only by convention; persistence code should copy it
    defensively rather than assume the runtime enforces immutability.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    provider: str
    family: str | None = None

    selectable: bool = True
    supported_efforts: tuple[str, ...] = Field(default_factory=tuple)
    effort_order: tuple[str, ...] | None = None

    relative_power: float | None = None
    relative_cost: float | None = None
    relative_latency: float | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def effort_order_matches_catalog(self) -> Self:
        """Require an explicit complete ordering before routing can rank efforts."""
        if self.effort_order is None:
            return self
        if len(set(self.effort_order)) != len(self.effort_order):
            raise ValueError("effort_order must not contain duplicates")
        if set(self.effort_order) != set(self.supported_efforts):
            raise ValueError("effort_order must contain every supported effort exactly once")
        return self
