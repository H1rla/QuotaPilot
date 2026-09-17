"""CapabilitySet: what an account can currently do."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from quotapilot.domain.model import AIModel


class CapabilitySet(BaseModel):
    """The models and features an account currently has access to.

    Unknown models must still be surfaced (e.g. via `routing_status` in
    `AIModel.metadata`) rather than dropped or rejected.

    `models` is a `tuple` (not `list`) so this collection can't be mutated
    in place; since `AIModel` is itself frozen, `models` is genuinely
    deep-immutable. See `AIModel`'s docstring for the `metadata`-is-only-
    shallow caveat, which still applies to `CapabilitySet.metadata` here.
    """

    model_config = ConfigDict(frozen=True)

    models: tuple[AIModel, ...]
    supports_reasoning_effort: bool = False
    supports_credits: bool = False
    supports_model_selection: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
