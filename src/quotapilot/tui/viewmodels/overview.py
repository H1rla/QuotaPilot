"""Persisted-first, safely refreshed Overview state."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from quotapilot.domain.usage import UsageSnapshot
from quotapilot.observability.models import SnapshotSource, StatusReport
from quotapilot.providers.base import (
    ProviderAuthentication,
    ProviderConnection,
    ProviderInspection,
)
from quotapilot.services.provider_status import ProviderStatus, ProviderStatusService
from quotapilot.tui.state import (
    OverviewState,
    ViewStatus,
    map_overview_state,
    provider_status_after_report,
    utc_now,
)


class _StatusService(Protocol):
    async def get_status(
        self,
        *,
        now: datetime,
        provider: str | None = None,
        refresh_provider: _UsageCapture | None = None,
    ) -> StatusReport | None: ...


class _UsageCapture(Protocol):
    async def capture_usage(self) -> UsageSnapshot: ...


class _StatusInspector(_UsageCapture, Protocol):
    async def inspect_status(self) -> ProviderInspection: ...


PublishState = Callable[[OverviewState], None]


class OverviewViewModel:
    """Coordinate local state and provider reads outside Textual widgets."""

    def __init__(
        self,
        status_service: _StatusService,
        provider_status_service: ProviderStatusService,
        provider: _StatusInspector,
        *,
        selected_provider: str | None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._status_service = status_service
        self._provider_status_service = provider_status_service
        self._provider = provider
        self._selected_provider = selected_provider
        self._clock = clock
        self._report: StatusReport | None = None
        self._provider_status: ProviderStatus | None = None
        self._active = False
        self._startup_started = False
        self.state = OverviewState()

    @property
    def active(self) -> bool:
        return self._active

    async def startup(self, publish: PublishState) -> bool:
        """Publish persisted state, then attempt one eligible live refresh."""
        if self._startup_started or self._active:
            return False
        self._startup_started = True
        self._active = True
        self._set_state(ViewStatus.LOADING, publish, message_id="overview.loading")
        try:
            try:
                self._report = await self._status_service.get_status(
                    now=self._clock(),
                    provider=self._selected_provider,
                )
            except Exception:  # noqa: BLE001 - stable presentation boundary
                self._set_state(
                    ViewStatus.ERROR,
                    publish,
                    message_id="overview.local_error",
                )
                return True

            self._set_state(
                ViewStatus.READY if self._report is not None else ViewStatus.EMPTY,
                publish,
                message_id=(None if self._report is not None else "overview.no_snapshot"),
            )
            await self._inspect_and_refresh(publish)
            return True
        finally:
            self._active = False

    async def refresh(self, publish: PublishState) -> bool:
        """Run the same safe provider inspection/refresh path as startup."""
        if self._active:
            return False
        self._active = True
        try:
            await self._inspect_and_refresh(publish)
            return True
        finally:
            self._active = False

    async def _inspect_and_refresh(self, publish: PublishState) -> None:
        try:
            self._provider_status = await self._provider_status_service.get_status(
                self._provider,
                self._report,
            )
        except Exception:  # noqa: BLE001 - do not expose adapter detail
            self._set_state(
                ViewStatus.READY if self._report is not None else ViewStatus.UNAVAILABLE,
                publish,
                message_id="overview.provider_unavailable",
            )
            return

        if not self._refresh_is_safe(self._provider_status):
            self._set_state(
                ViewStatus.READY if self._report is not None else ViewStatus.EMPTY,
                publish,
                message_id=self._unsafe_message(self._provider_status),
            )
            return

        self._set_state(
            ViewStatus.REFRESHING,
            publish,
            refreshing=True,
            message_id="overview.refreshing",
        )
        previous_report = self._report
        try:
            refreshed = await self._status_service.get_status(
                now=self._clock(),
                provider=self._selected_provider,
                refresh_provider=self._provider,
            )
        except Exception:  # noqa: BLE001 - preserve prior privacy-safe state
            refreshed = previous_report
            message_id = "overview.refresh_failed"
        else:
            message_id = None
            if refreshed is None:
                message_id = "overview.refresh_failed"
                refreshed = previous_report
            elif refreshed.source is SnapshotSource.PERSISTED_FALLBACK:
                message_id = "overview.refresh_failed"

        self._report = refreshed
        self._provider_status = provider_status_after_report(
            self._provider_status,
            self._report,
        )
        self._set_state(
            ViewStatus.READY if self._report is not None else ViewStatus.UNAVAILABLE,
            publish,
            message_id=message_id,
        )

    def _refresh_is_safe(self, status: ProviderStatus) -> bool:
        selected = self._selected_provider
        return (
            selected in {None, "openai-codex"}
            and status.connection is ProviderConnection.CONNECTED
            and status.authentication is ProviderAuthentication.AUTHENTICATED
        )

    @staticmethod
    def _unsafe_message(status: ProviderStatus) -> str:
        if status.authentication is ProviderAuthentication.NOT_AUTHENTICATED:
            return "overview.not_authenticated"
        if status.connection is ProviderConnection.UNAVAILABLE:
            return "overview.provider_unavailable"
        return "overview.provider_unknown"

    def _set_state(
        self,
        status: ViewStatus,
        publish: PublishState,
        *,
        refreshing: bool = False,
        message_id: str | None = None,
    ) -> None:
        self.state = map_overview_state(
            self._report,
            self._provider_status,
            status=status,
            refreshing=refreshing,
            message_id=message_id,
        )
        publish(self.state)
