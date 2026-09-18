"""Compose persisted/live snapshots into one privacy-safe operational status."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from quotapilot.budget.engine import BudgetEngine
from quotapilot.capabilities.enrichment import CapabilityEnricher, capability_views
from quotapilot.capabilities.models import ProfileFreshness
from quotapilot.capabilities.registry import ModelProfileRegistry
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.history.repository import SnapshotRepository
from quotapilot.observability.models import (
    ProfileStatus,
    SnapshotSource,
    StatusPool,
    StatusReport,
    WaybarPayload,
)


class _UsageCapture(Protocol):
    async def capture_usage(self) -> UsageSnapshot: ...


class StatusService:
    """Use existing budget/enrichment contracts; never duplicate their policy."""

    def __init__(
        self,
        repository: SnapshotRepository,
        budget_engine: BudgetEngine,
        capability_enricher: CapabilityEnricher,
        profile_registry: ModelProfileRegistry,
    ) -> None:
        self._repository = repository
        self._budget_engine = budget_engine
        self._capability_enricher = capability_enricher
        self._profile_registry = profile_registry

    async def get_status(
        self,
        *,
        now: datetime,
        provider: str | None = None,
        refresh_provider: _UsageCapture | None = None,
    ) -> StatusReport | None:
        source = SnapshotSource.PERSISTED
        warnings: list[str] = []
        snapshot: UsageSnapshot | None = None

        if refresh_provider is not None:
            try:
                snapshot = await refresh_provider.capture_usage()
                await self._repository.save_snapshot(snapshot)
                source = SnapshotSource.LIVE_CAPTURE
            except Exception:  # noqa: BLE001 - fallback is the product boundary
                # Provider details can contain unsafe or unstable text. Preserve
                # the useful cached observation and expose only a stable warning.
                source = SnapshotSource.PERSISTED_FALLBACK
                warnings.append("provider_refresh_failed_using_persisted_snapshot")

        if snapshot is None:
            snapshot = await self._repository.get_latest_snapshot(provider=provider)
        if snapshot is None:
            return None

        budget = self._budget_engine.evaluate(snapshot, now=now)
        evaluated_on = now.astimezone(UTC).date()
        enriched = self._capability_enricher.enrich(
            snapshot.account.capabilities,
            self._profile_registry,
            evaluated_on=evaluated_on,
        )
        views = capability_views(enriched)
        matched_freshness = tuple(
            view.freshness for view in views if view.freshness is not None
        )
        if ProfileFreshness.STALE in matched_freshness:
            freshness = ProfileFreshness.STALE
        elif ProfileFreshness.UNKNOWN in matched_freshness or not matched_freshness:
            freshness = ProfileFreshness.UNKNOWN
        else:
            freshness = ProfileFreshness.FRESH

        profile = ProfileStatus(
            evaluated_on=evaluated_on,
            freshness=freshness,
            model_count=len(views),
            routable_model_count=sum(view.routable for view in views),
            profiled_model_count=sum(view.profile_name is not None for view in views),
        )
        if freshness is ProfileFreshness.STALE:
            warnings.append("model_profile_stale")
        warnings.extend(budget.warnings)

        return StatusReport(
            provider=snapshot.account.provider,
            source=source,
            captured_at=snapshot.captured_at,
            evaluated_at=now,
            snapshot_age_seconds=budget.snapshot_age_seconds,
            is_stale=budget.is_stale,
            pools=tuple(
                StatusPool(
                    pool_id=pool.pool_id,
                    name=pool.pool_name,
                    state=pool.state,
                    used_fraction=pool.actual_usage,
                    remaining_fraction=pool.remaining_fraction,
                    today_budget_fraction=pool.today_budget_fraction,
                    resets_at=pool.resets_at,
                    warnings=pool.warnings,
                )
                for pool in budget.pools
            ),
            effective_pressure=budget.effective_pressure,
            binding_pool_id=budget.binding_pool_id,
            profile=profile,
            warnings=tuple(dict.fromkeys(warnings)),
        )


def waybar_payload(report: StatusReport) -> WaybarPayload:
    """Render status using only status fields; never re-evaluate quota policy."""
    binding = next(
        (pool for pool in report.pools if pool.pool_id == report.binding_pool_id),
        report.pools[0] if report.pools else None,
    )
    remaining = binding.remaining_fraction if binding is not None else None
    text = "QP ?" if remaining is None else f"QP {remaining:.0%}"
    state = binding.state.value if binding is not None else "unknown"
    css_class = "stale" if report.is_stale else state.replace("_", "-")
    lines = [
        f"Source: {report.source.value}",
        f"Snapshot: {'STALE' if report.is_stale else 'current'}",
        f"State: {state.upper()}",
        "Remaining: " + ("unknown" if remaining is None else f"{remaining:.1%}"),
        "Pressure: "
        + (
            "unknown"
            if report.effective_pressure is None
            else f"{report.effective_pressure:.2f}"
        ),
        f"Profiles: {report.profile.freshness.value}",
    ]
    if report.warnings:
        lines.append("Warnings: " + ", ".join(report.warnings))
    return WaybarPayload(text=text, tooltip="\n".join(lines), class_name=css_class)


def waybar_error(message: str = "operational state unavailable") -> WaybarPayload:
    """Return a stable valid payload without reflecting unsafe exception text."""
    return WaybarPayload(
        text="QP ?",
        tooltip=f"QuotaPilot: {message}",
        class_name="error",
    )
