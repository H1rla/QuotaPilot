"""Pure deterministic merge of live capabilities and versioned profiles."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any

from quotapilot.capabilities.models import (
    ModelCapabilityView,
    ProfileFreshness,
    ProfileMatch,
)
from quotapilot.capabilities.registry import ModelProfileRegistry
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.model import AIModel

_ROUTING_FIELDS = (
    "relative_power",
    "relative_cost",
    "relative_latency",
    "effort_order",
)


class CapabilityEnricher:
    """Fill only missing routing fields; existing capability values always win."""

    def enrich(
        self,
        capabilities: CapabilitySet,
        registry: ModelProfileRegistry,
        *,
        evaluated_on: date,
    ) -> CapabilitySet:
        models = tuple(
            self._enrich_model(model, registry, evaluated_on=evaluated_on)
            for model in capabilities.models
        )
        metadata = deepcopy(capabilities.metadata)
        metadata["capability_enrichment"] = {
            "evaluated_on": evaluated_on.isoformat(),
            "matched_models": sum(
                bool(model.metadata.get("routing_profile", {}).get("matched"))
                for model in models
            ),
            "enriched_models": sum(
                bool(model.metadata.get("routing_profile", {}).get("applied_fields"))
                for model in models
            ),
        }
        return capabilities.model_copy(update={"models": models, "metadata": metadata})

    def _enrich_model(
        self,
        model: AIModel,
        registry: ModelProfileRegistry,
        *,
        evaluated_on: date,
    ) -> AIModel:
        matches = registry.matches(model.provider, model.id, evaluated_on=evaluated_on)
        metadata = deepcopy(model.metadata)
        previous_profile = metadata.get("routing_profile", {})
        previous_sources = previous_profile.get("field_sources", {})
        field_sources: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []
        updates: dict[str, Any] = {}

        for field in _ROUTING_FIELDS:
            if getattr(model, field) is not None:
                previous = previous_sources.get(field)
                field_sources[field] = (
                    deepcopy(previous)
                    if isinstance(previous, dict)
                    else {"origin": "capability", "source": "provider"}
                )

        for match in matches:
            profile = match.profile
            if match.freshness is not ProfileFreshness.FRESH:
                warnings.append(
                    f"profile:{match.profile_name}:{match.freshness.value}:not_applied"
                )
                continue
            for field in _ROUTING_FIELDS:
                if field in updates or getattr(model, field) is not None:
                    profile_value = getattr(profile, field)
                    if profile_value is not None and getattr(model, field) is not None:
                        warnings.append(f"{field}:existing_capability_preserved")
                    continue
                value = getattr(profile, field)
                if value is None:
                    continue
                if field == "effort_order" and set(value) != set(model.supported_efforts):
                    warnings.append("effort_order:profile_catalog_mismatch:not_applied")
                    continue
                updates[field] = value
                field_sources[field] = self._profile_source(match)

        metadata["routing_profile"] = {
            "matched": bool(matches),
            "applied_fields": tuple(updates),
            "field_sources": field_sources,
            "matches": tuple(self._match_summary(match) for match in matches),
            "warnings": tuple(dict.fromkeys(warnings)),
        }
        updates["metadata"] = metadata
        return model.model_copy(update=updates)

    @staticmethod
    def _profile_source(match: ProfileMatch) -> dict[str, Any]:
        provenance = match.profile.provenance
        return {
            "origin": "profile",
            "source": provenance.source.value,
            "confidence": provenance.confidence.value,
            "evidence": provenance.evidence,
            "verified_at": match.verified_at.isoformat(),
            "freshness": match.freshness.value,
            "product": match.product,
            "profile": match.profile_name,
        }

    @staticmethod
    def _match_summary(match: ProfileMatch) -> dict[str, Any]:
        return {
            "profile": match.profile_name,
            "product": match.product,
            "schema_version": match.schema_version,
            "verified_at": match.verified_at.isoformat(),
            "expires_after_days": match.expires_after_days,
            "freshness": match.freshness.value,
            "source": match.profile.provenance.source.value,
            "confidence": match.profile.provenance.confidence.value,
            "evidence": match.profile.provenance.evidence,
        }


def capability_views(capabilities: CapabilitySet) -> tuple[ModelCapabilityView, ...]:
    """Build privacy-safe model/profile observability without raw metadata."""
    views: list[ModelCapabilityView] = []
    for model in capabilities.models:
        routing_profile = model.metadata.get("routing_profile", {})
        sources = routing_profile.get("field_sources", {})
        profile_sources = [
            value for value in sources.values() if value.get("origin") == "profile"
        ]
        primary = profile_sources[0] if profile_sources else None
        matches = routing_profile.get("matches", ())
        match = matches[0] if matches else None
        profile_context = primary or match
        views.append(
            ModelCapabilityView(
                model_id=model.id,
                provider=model.provider,
                selectable=model.selectable,
                routable=model.selectable and model.relative_power is not None,
                relative_power=model.relative_power,
                relative_cost=model.relative_cost,
                relative_latency=model.relative_latency,
                effort_order=model.effort_order,
                field_sources={
                    field: (
                        str(source.get("source", "unknown"))
                        if source.get("origin") == "capability"
                        else "profile/" + str(source.get("source", "unknown"))
                    )
                    for field, source in sources.items()
                },
                profile_name=(
                    profile_context.get("profile") if profile_context else None
                ),
                profile_source=(
                    profile_context.get("source") if profile_context else None
                ),
                profile_confidence=(
                    profile_context.get("confidence") if profile_context else None
                ),
                profile_evidence=tuple(
                    profile_context.get("evidence", ()) if profile_context else ()
                ),
                verified_at=(
                    profile_context.get("verified_at") if profile_context else None
                ),
                freshness=(profile_context or {}).get("freshness"),
                warnings=tuple(routing_profile.get("warnings", ())),
            )
        )
    return tuple(views)
