"""Immutable presentation state shared by TUI view models and widgets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from quotapilot.budget.models import BudgetState
from quotapilot.observability.models import SnapshotSource, StatusPool, StatusReport
from quotapilot.providers.base import ProviderAuthentication, ProviderConnection
from quotapilot.services.provider_status import ProviderStatus


class Destination(StrEnum):
    OVERVIEW = "overview"
    ROUTE = "route"
    EXECUTE = "execute"
    USAGE = "usage"
    MODELS = "models"
    HISTORY = "history"
    SETTINGS = "settings"
    DOCTOR = "doctor"


DESTINATIONS: tuple[Destination, ...] = tuple(Destination)


class LayoutMode(StrEnum):
    WIDE = "wide"
    STANDARD = "standard"
    COMPACT = "compact"
    CONSTRAINED = "constrained"


class VerticalMode(StrEnum):
    NORMAL = "normal"
    SHORT = "short"
    VERY_SHORT = "very_short"
    UNSAFE = "unsafe"


class ViewStatus(StrEnum):
    INITIAL = "initial"
    LOADING = "loading"
    READY = "ready"
    REFRESHING = "refreshing"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class OverviewState:
    status: ViewStatus = ViewStatus.INITIAL
    pool_name: str | None = None
    remaining_fraction: float | None = None
    used_fraction: float | None = None
    budget_state: BudgetState = BudgetState.UNKNOWN
    reset_seconds: int | None = None
    today_budget_fraction: float | None = None
    pressure: float | None = None
    source: SnapshotSource | None = None
    snapshot_age_seconds: float | None = None
    stale: bool = False
    provider: str = "openai-codex"
    connection: ProviderConnection = ProviderConnection.UNKNOWN
    authentication: ProviderAuthentication = ProviderAuthentication.UNKNOWN
    using_persisted_data: bool = False
    refreshing: bool = False
    message_id: str | None = None

    @property
    def available(self) -> bool:
        return self.source is not None


def horizontal_mode(columns: int) -> LayoutMode:
    if columns >= 120:
        return LayoutMode.WIDE
    if columns >= 88:
        return LayoutMode.STANDARD
    if columns >= 60:
        return LayoutMode.COMPACT
    return LayoutMode.CONSTRAINED


def vertical_mode(rows: int) -> VerticalMode:
    if rows >= 30:
        return VerticalMode.NORMAL
    if rows >= 24:
        return VerticalMode.SHORT
    if rows >= 18:
        return VerticalMode.VERY_SHORT
    return VerticalMode.UNSAFE


def _binding_pool(report: StatusReport) -> StatusPool | None:
    return next(
        (pool for pool in report.pools if pool.pool_id == report.binding_pool_id),
        report.pools[0] if report.pools else None,
    )


def map_overview_state(
    report: StatusReport | None,
    provider_status: ProviderStatus | None,
    *,
    status: ViewStatus,
    refreshing: bool = False,
    message_id: str | None = None,
) -> OverviewState:
    """Map privacy-safe service results without inventing missing values."""
    pool = _binding_pool(report) if report is not None else None
    reset_seconds: int | None = None
    if report is not None and pool is not None and pool.resets_at is not None:
        reset_seconds = max(
            0,
            round(
                (
                    pool.resets_at.astimezone(UTC) - report.evaluated_at.astimezone(UTC)
                ).total_seconds()
            ),
        )
    return OverviewState(
        status=status,
        pool_name=pool.name if pool is not None else None,
        remaining_fraction=pool.remaining_fraction if pool is not None else None,
        used_fraction=pool.used_fraction if pool is not None else None,
        budget_state=pool.state if pool is not None else BudgetState.UNKNOWN,
        reset_seconds=reset_seconds,
        today_budget_fraction=(pool.today_budget_fraction if pool is not None else None),
        pressure=report.effective_pressure if report is not None else None,
        source=report.source if report is not None else None,
        snapshot_age_seconds=(report.snapshot_age_seconds if report is not None else None),
        stale=report.is_stale if report is not None else False,
        provider=(
            provider_status.provider
            if provider_status is not None
            else report.provider
            if report is not None
            else "openai-codex"
        ),
        connection=(
            provider_status.connection
            if provider_status is not None
            else ProviderConnection.UNKNOWN
        ),
        authentication=(
            provider_status.authentication
            if provider_status is not None
            else ProviderAuthentication.UNKNOWN
        ),
        using_persisted_data=(
            provider_status.using_persisted_data
            if provider_status is not None
            else report is not None
            and report.source in {SnapshotSource.PERSISTED, SnapshotSource.PERSISTED_FALLBACK}
        ),
        refreshing=refreshing,
        message_id=message_id,
    )


def provider_status_after_report(
    provider_status: ProviderStatus,
    report: StatusReport | None,
) -> ProviderStatus:
    """Update provider display facts without performing a second inspection."""
    if report is None:
        return provider_status
    return provider_status.model_copy(
        update={
            "last_refresh_at": report.captured_at,
            "using_persisted_data": report.source
            in {SnapshotSource.PERSISTED, SnapshotSource.PERSISTED_FALLBACK},
            "stale": report.is_stale,
        }
    )


def utc_now() -> datetime:
    return datetime.now(UTC)
