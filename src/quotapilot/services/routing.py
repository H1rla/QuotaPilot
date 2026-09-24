"""Orchestrate persisted snapshots, budgeting, profiling, and pure routing."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from quotapilot.budget.engine import BudgetEngine
from quotapilot.budget.models import BudgetReport
from quotapilot.capabilities.enrichment import CapabilityEnricher
from quotapilot.capabilities.registry import ModelProfileRegistry
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.history.repository import SnapshotRepository
from quotapilot.routing.engine import RoutingEngine
from quotapilot.routing.models import (
    RecommendationConfidence,
    RoutingRecommendation,
    TaskProfile,
    TaskProfileOverrides,
)
from quotapilot.routing.profiler import TaskProfiler


@dataclass(frozen=True, slots=True)
class RoutingContext:
    """Advisory recommendation plus the exact normalized inputs it used."""

    provider: str
    recommendation: RoutingRecommendation
    budget_report: BudgetReport
    capabilities: CapabilitySet
    snapshot_captured_at: datetime


class RoutingService:
    """Build an advisory route from the latest coherent persisted snapshot."""

    def __init__(
        self,
        repository: SnapshotRepository,
        budget_engine: BudgetEngine,
        routing_engine: RoutingEngine,
        profiler: TaskProfiler,
        capability_enricher: CapabilityEnricher | None = None,
        profile_registry: ModelProfileRegistry | None = None,
    ) -> None:
        self._repository = repository
        self._budget_engine = budget_engine
        self._routing_engine = routing_engine
        self._profiler = profiler
        if (capability_enricher is None) != (profile_registry is None):
            raise ValueError("capability enricher and profile registry must be supplied together")
        self._capability_enricher = capability_enricher
        self._profile_registry = profile_registry

    async def recommend_latest(
        self,
        summary: str,
        *,
        now: datetime,
        overrides: TaskProfileOverrides | None = None,
        provider: str | None = None,
    ) -> RoutingRecommendation | None:
        context = await self.recommend_latest_context(
            summary,
            now=now,
            overrides=overrides,
            provider=provider,
        )
        return context.recommendation if context is not None else None

    async def recommend_latest_context(
        self,
        summary: str,
        *,
        now: datetime,
        overrides: TaskProfileOverrides | None = None,
        provider: str | None = None,
    ) -> RoutingContext | None:
        """Return the latest recommendation with its budget/capability context."""
        snapshot = await self._repository.get_latest_snapshot(provider=provider)
        if snapshot is None:
            return None
        return await asyncio.to_thread(
            self.recommend_snapshot,
            snapshot,
            summary,
            now=now,
            overrides=overrides,
        )

    def recommend_snapshot(
        self,
        snapshot: UsageSnapshot,
        summary: str,
        *,
        now: datetime,
        overrides: TaskProfileOverrides | None = None,
    ) -> RoutingContext:
        """Route one coherent snapshot without provider or persistence I/O."""
        profile = self._profiler.profile(summary, overrides)
        return self.recommend_profile_snapshot(snapshot, profile, now=now)

    def recommend_profile_snapshot(
        self,
        snapshot: UsageSnapshot,
        profile: TaskProfile,
        *,
        now: datetime,
    ) -> RoutingContext:
        """Route one snapshot with an already-audited deterministic profile."""
        budget = self._budget_engine.evaluate(snapshot, now=now)
        capabilities = snapshot.account.capabilities
        if self._capability_enricher is not None and self._profile_registry is not None:
            capabilities = self._capability_enricher.enrich(
                capabilities,
                self._profile_registry,
                evaluated_on=now.astimezone(UTC).date(),
            )
        recommendation = self._routing_engine.recommend(
            profile, budget, capabilities
        )
        recommendation = self._attach_profile_provenance(recommendation, capabilities)
        return RoutingContext(
            provider=snapshot.account.provider,
            recommendation=recommendation,
            budget_report=budget,
            capabilities=capabilities,
            snapshot_captured_at=snapshot.captured_at,
        )

    @staticmethod
    def _attach_profile_provenance(
        recommendation: RoutingRecommendation,
        capabilities: CapabilitySet,
    ) -> RoutingRecommendation:
        selected = next(
            model
            for model in capabilities.models
            if model.id == recommendation.selected_model_id
        )
        profile = selected.metadata.get("routing_profile", {})
        field_sources = profile.get("field_sources", {})
        enriched = [
            source
            for source in field_sources.values()
            if source.get("origin") == "profile"
        ]
        if not enriched:
            return recommendation

        source = enriched[0]
        explanation = recommendation.explanation + (
            "Capability metadata came from the versioned local profile "
            f"{source.get('profile')} (source={source.get('source')}, "
            f"confidence={source.get('confidence')}, "
            f"verified_at={source.get('verified_at')}, "
            f"freshness={source.get('freshness')}).",
        )
        warnings = recommendation.warnings + (
            "capability_metadata_from_local_profile:" + str(source.get("confidence")),
        )
        confidence = recommendation.confidence
        if source.get("confidence") in {"low", "provisional"}:
            confidence = RecommendationConfidence.LOW
        elif (
            source.get("confidence") == "medium"
            and confidence is RecommendationConfidence.HIGH
        ):
            confidence = RecommendationConfidence.MEDIUM
        return recommendation.model_copy(
            update={
                "explanation": explanation,
                "warnings": tuple(dict.fromkeys(warnings)),
                "confidence": confidence,
            }
        )
