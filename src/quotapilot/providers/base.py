"""Provider protocol: the boundary every usage provider must implement.

Provider-specific response structures must not leak past this boundary into
the budget/routing layers — adapters normalize into `quotapilot.domain` types.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict

from quotapilot.domain.account import AccountInfo
from quotapilot.domain.model import AIModel
from quotapilot.domain.quota import QuotaBinding, QuotaPool
from quotapilot.domain.usage import UsageSnapshot


class ProviderHealth(BaseModel):
    """Result of a provider connectivity/health check."""

    model_config = ConfigDict(frozen=True)

    provider: str
    ok: bool
    detail: str | None = None
    checked_at: AwareDatetime


class ProviderConnection(StrEnum):
    CONNECTED = "connected"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class ProviderAuthentication(StrEnum):
    AUTHENTICATED = "authenticated"
    NOT_AUTHENTICATED = "not_authenticated"
    UNKNOWN = "unknown"


class ProviderInspection(BaseModel):
    """Provider-boundary facts with no account identity or raw payload."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    provider: str
    connection: ProviderConnection
    authentication: ProviderAuthentication
    checked_at: AwareDatetime


class UsageProvider(Protocol):
    """Provider-independent interface for retrieving account/quota state.

    `capture_usage()` is the atomic entry point: implementations must
    return a single, internally coherent `UsageSnapshot` — account,
    quota pools, and quota bindings all observed together, sharing one
    `captured_at`, with bindings referencing only pools present in that
    same snapshot. Individual getter calls are independent point reads even
    when implemented as wrappers around `capture_usage()`; callers must not
    combine sequential getter results and call that an atomic observation.
    Persistence and any other coherent consumer must call `capture_usage()`.
    """

    async def capture_usage(self) -> UsageSnapshot: ...

    async def get_account(self) -> AccountInfo: ...

    async def get_models(self) -> list[AIModel]: ...

    async def get_quota_pools(self) -> list[QuotaPool]: ...

    async def get_quota_bindings(self) -> list[QuotaBinding]: ...

    async def healthcheck(self) -> ProviderHealth: ...

    async def inspect_status(self) -> ProviderInspection: ...
