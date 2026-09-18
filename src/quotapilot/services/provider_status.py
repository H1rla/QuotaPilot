"""Privacy-safe provider connection/authentication status composition."""

from __future__ import annotations

from typing import Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict

from quotapilot.observability.models import SnapshotSource, StatusReport
from quotapilot.providers.base import (
    ProviderAuthentication,
    ProviderConnection,
    ProviderInspection,
)


class ProviderStatus(BaseModel):
    """UI-safe provider and persisted-data status."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    provider: str
    connection: ProviderConnection
    authentication: ProviderAuthentication
    checked_at: AwareDatetime | None = None
    last_refresh_at: AwareDatetime | None = None
    using_persisted_data: bool = False
    stale: bool = False


class _StatusInspector(Protocol):
    async def inspect_status(self) -> ProviderInspection: ...


class ProviderStatusService:
    """Combine a bounded provider inspection with privacy-safe snapshot status."""

    async def get_status(
        self,
        inspector: _StatusInspector,
        report: StatusReport | None,
    ) -> ProviderStatus:
        inspection = await inspector.inspect_status()
        return ProviderStatus(
            provider=inspection.provider,
            connection=inspection.connection,
            authentication=inspection.authentication,
            checked_at=inspection.checked_at,
            last_refresh_at=report.captured_at if report is not None else None,
            using_persisted_data=(
                report is not None
                and report.source in {SnapshotSource.PERSISTED, SnapshotSource.PERSISTED_FALLBACK}
            ),
            stale=report.is_stale if report is not None else False,
        )
