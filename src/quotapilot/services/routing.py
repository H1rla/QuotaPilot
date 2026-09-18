"""Orchestrate persisted snapshots, budgeting, profiling, and pure routing."""

from __future__ import annotations

from datetime import UTC, datetime

from quotapilot.budget.engine import BudgetEngine
from quotapilot.capabilities.enrichment import CapabilityEnricher
from quotapilot.capabilities.registry import ModelProfileRegistry
from quotapilot.domain.capability import CapabilitySet
from quotapilot.history.repository import SnapshotRepository
from quotapilot.routing.engine import RoutingEngine
from quotapilot.routing.models import (
    RecommendationConfidence,
    RoutingRecommendation,
    TaskProfileOverrides,
)
from quotapilot.routing.profiler import TaskProfiler


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
        snapshot = await self._repository.get_latest_snapshot(provider=provider)
        if snapshot is None:
            return None
        budget = self._budget_engine.evaluate(snapshot, now=now)
        profile = self._profiler.profile(summary, overrides)
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
        return self._attach_profile_provenance(recommendation, capabilities)

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
