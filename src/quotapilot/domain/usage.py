"""UsageSnapshot: a point-in-time capture of account, quota pools, and bindings."""

from __future__ import annotations

from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from quotapilot.domain.account import AccountInfo
from quotapilot.domain.quota import QuotaBinding, QuotaPool


class UsageSnapshot(BaseModel):
    """A persistable, point-in-time capture of provider usage state.

    Must be internally coherent: `quota_bindings` must only reference
    `quota_pools` present in this same snapshot (providers are responsible
    for this through `UsageProvider.capture_usage()`), and every field must
    come from one atomic capture operation sharing one `captured_at`.

    `metadata` is a capture-level envelope for provider observations that
    cannot yet be normalized into any domain field (unknown top-level
    response fields, structures with no current mapping). Provider adapters
    must sanitize it before constructing the snapshot. Only shallowly
    immutable — see `AIModel`'s docstring.
    """

    model_config = ConfigDict(frozen=True)

    account: AccountInfo
    quota_pools: tuple[QuotaPool, ...]
    quota_bindings: tuple[QuotaBinding, ...]
    captured_at: AwareDatetime
    metadata: dict[str, Any] = Field(default_factory=dict)
