"""AccountInfo: provider account metadata."""

from __future__ import annotations

from pydantic import AwareDatetime, BaseModel, ConfigDict

from quotapilot.domain.capability import CapabilitySet


class AccountInfo(BaseModel):
    """Provider account metadata.

    `plan_name` is informational only; business logic must not branch on it.
    """

    model_config = ConfigDict(frozen=True)

    provider: str
    account_id: str | None = None
    plan_name: str | None = None
    capabilities: CapabilitySet
    observed_at: AwareDatetime
