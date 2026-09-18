"""Deterministic profile merge and routing integration tests."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from quotapilot.budget.models import BudgetReport
from quotapilot.capabilities.enrichment import CapabilityEnricher, capability_views
from quotapilot.capabilities.loader import default_profile_directory
from quotapilot.capabilities.models import (
    MetricProvenance,
    ModelProfile,
    ModelProfileDocument,
    ProfileFreshness,
    ProvenanceConfidence,
    ProvenanceSource,
)
from quotapilot.capabilities.registry import ModelProfileRegistry
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.model import AIModel
from quotapilot.providers.openai_codex.models import ModelListResponse, parse_codex_response
from quotapilot.providers.openai_codex.parser import normalize_models
from quotapilot.routing.engine import RoutingEngine
from quotapilot.routing.errors import NoRoutableModelError
from quotapilot.routing.profiler import TaskProfiler

NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)


def _document(
    *,
    verified_at: date = date(2026, 9, 18),
    expires_after_days: int | None = 30,
    model_id: str = "model-a",
    profile: ModelProfile | None = None,
) -> ModelProfileDocument:
    return ModelProfileDocument(
        schema_version=1,
        provider="test-provider",
        product="test-product",
        verified_at=verified_at,
        expires_after_days=expires_after_days,
        models={
            model_id: profile
            or ModelProfile(
                relative_power=0.7,
                relative_cost=0.4,
                relative_latency=0.3,
                effort_order=("small", "large"),
                provenance=MetricProvenance(
                    source=ProvenanceSource.MANUAL,
                    confidence=ProvenanceConfidence.PROVISIONAL,
                    evidence=("Synthetic evidence.",),
                ),
            )
        },
    )


def _capabilities(*models: AIModel) -> CapabilitySet:
    return CapabilitySet(models=models, metadata={"nested": {"original": True}})


def _budget(pressure: float | None = 0.35) -> BudgetReport:
    return BudgetReport(
        captured_at=NOW,
        evaluated_at=NOW,
        snapshot_age_seconds=0.0,
        is_stale=False,
        reserve_fraction=0.1,
        timezone="UTC",
        pools=(),
        effective_pressure=pressure,
    )


def test_enrichment_fills_missing_fields_and_preserves_provenance() -> None:
    original = _capabilities(
        AIModel(
            id="model-a",
            provider="test-provider",
            supported_efforts=("small", "large"),
        )
    )
    registry = ModelProfileRegistry((("profile.yaml", _document()),))

    enriched = CapabilityEnricher().enrich(
        original, registry, evaluated_on=date(2026, 9, 18)
    )
    model = enriched.models[0]
    profile = model.metadata["routing_profile"]

    assert model.relative_power == 0.7
    assert model.relative_cost == 0.4
    assert model.relative_latency == 0.3
    assert model.effort_order == ("small", "large")
    assert set(profile["applied_fields"]) == {
        "relative_power",
        "relative_cost",
        "relative_latency",
        "effort_order",
    }
    assert profile["field_sources"]["relative_power"]["source"] == "manual"
    view = capability_views(enriched)[0]
    assert view.freshness is ProfileFreshness.FRESH
    assert view.field_sources["relative_power"] == "profile/manual"
    assert view.profile_name == "profile.yaml"
    assert view.profile_evidence == ("Synthetic evidence.",)


def test_existing_provider_metadata_wins_without_mutating_original() -> None:
    original = _capabilities(
        AIModel(
            id="model-a",
            provider="test-provider",
            supported_efforts=("small", "large"),
            effort_order=("small", "large"),
            relative_power=0.9,
            relative_cost=0.8,
            relative_latency=0.6,
            metadata={"nested": {"provider": True}},
        )
    )
    before = original.model_dump(mode="python")
    registry = ModelProfileRegistry((("profile.yaml", _document()),))

    enriched = CapabilityEnricher().enrich(
        original, registry, evaluated_on=date(2026, 9, 18)
    )

    assert enriched.models[0].relative_power == 0.9
    assert enriched.models[0].relative_cost == 0.8
    assert enriched.models[0].relative_latency == 0.6
    assert enriched.models[0].metadata["routing_profile"]["applied_fields"] == ()
    assert capability_views(enriched)[0].field_sources["relative_power"] == "provider"
    assert original.model_dump(mode="python") == before
    assert "routing_profile" not in original.models[0].metadata


def test_unknown_model_is_retained_without_substring_guessing() -> None:
    original = _capabilities(
        AIModel(id="model-a-next", provider="test-provider", supported_efforts=("small",))
    )
    registry = ModelProfileRegistry((("profile.yaml", _document()),))

    enriched = CapabilityEnricher().enrich(
        original, registry, evaluated_on=date(2026, 9, 18)
    )

    assert enriched.models[0].id == "model-a-next"
    assert enriched.models[0].relative_power is None
    assert enriched.models[0].metadata["routing_profile"]["matched"] is False


def test_partial_profile_and_effort_catalog_mismatch_are_conservative() -> None:
    profile = ModelProfile(
        relative_power=0.6,
        effort_order=("small", "large"),
        provenance=MetricProvenance(
            source=ProvenanceSource.MANUAL,
            confidence=ProvenanceConfidence.LOW,
            evidence=("Partial synthetic evidence.",),
        ),
    )
    registry = ModelProfileRegistry(
        (("partial.yaml", _document(profile=profile)),)
    )
    original = _capabilities(
        AIModel(
            id="model-a",
            provider="test-provider",
            supported_efforts=("small", "medium", "large"),
        )
    )

    enriched = CapabilityEnricher().enrich(
        original, registry, evaluated_on=date(2026, 9, 18)
    )
    model = enriched.models[0]

    assert model.relative_power == 0.6
    assert model.relative_cost is None
    assert model.effort_order is None
    assert (
        "effort_order:profile_catalog_mismatch:not_applied"
        in model.metadata["routing_profile"]["warnings"]
    )


@pytest.mark.parametrize(
    ("evaluated_on", "freshness"),
    [
        (date(2026, 10, 19), ProfileFreshness.STALE),
        (date(2026, 9, 17), ProfileFreshness.UNKNOWN),
    ],
)
def test_non_fresh_profile_is_visible_but_not_applied(
    evaluated_on: date, freshness: ProfileFreshness
) -> None:
    registry = ModelProfileRegistry((("profile.yaml", _document()),))
    original = _capabilities(
        AIModel(
            id="model-a",
            provider="test-provider",
            supported_efforts=("small", "large"),
        )
    )

    enriched = CapabilityEnricher().enrich(
        original, registry, evaluated_on=evaluated_on
    )
    view = capability_views(enriched)[0]

    assert enriched.models[0].relative_power is None
    assert view.freshness is freshness
    assert view.profile_source is ProvenanceSource.MANUAL
    assert view.profile_confidence is ProvenanceConfidence.PROVISIONAL
    assert view.verified_at == date(2026, 9, 18)
    assert any(freshness.value in warning for warning in view.warnings)


def test_enrichment_is_deterministic() -> None:
    registry = ModelProfileRegistry((("profile.yaml", _document()),))
    original = _capabilities(
        AIModel(
            id="model-a",
            provider="test-provider",
            supported_efforts=("small", "large"),
        )
    )
    enricher = CapabilityEnricher()

    assert enricher.enrich(
        original, registry, evaluated_on=date(2026, 9, 18)
    ) == enricher.enrich(original, registry, evaluated_on=date(2026, 9, 18))


def test_reenrichment_does_not_launder_profile_provenance_as_provider_truth() -> None:
    registry = ModelProfileRegistry((("profile.yaml", _document()),))
    original = _capabilities(
        AIModel(
            id="model-a",
            provider="test-provider",
            supported_efforts=("small", "large"),
        )
    )
    enricher = CapabilityEnricher()

    enriched = enricher.enrich(
        original, registry, evaluated_on=date(2026, 9, 18)
    )
    reenriched = enricher.enrich(
        enriched, registry, evaluated_on=date(2026, 9, 18)
    )

    source = reenriched.models[0].metadata["routing_profile"]["field_sources"][
        "relative_power"
    ]
    assert source["origin"] == "profile"
    assert source["source"] == "manual"


def test_routing_fails_before_and_succeeds_after_enrichment() -> None:
    original = _capabilities(
        AIModel(
            id="model-a",
            provider="test-provider",
            supported_efforts=("small", "large"),
        ),
        AIModel(id="unprofiled", provider="test-provider", supported_efforts=("small",)),
    )
    profile = TaskProfiler().profile("Implement a local helper")
    engine = RoutingEngine()

    with pytest.raises(NoRoutableModelError):
        engine.recommend(profile, _budget(), original)

    registry = ModelProfileRegistry((("profile.yaml", _document()),))
    enriched = CapabilityEnricher().enrich(
        original, registry, evaluated_on=date(2026, 9, 18)
    )
    recommendation = engine.recommend(profile, _budget(), enriched)

    assert recommendation.selected_model_id == "model-a"
    assert recommendation.selected_effort in {"small", "large"}
    assert enriched.models[1].relative_power is None


def test_initial_codex_profile_matches_only_verified_fixture_ids() -> None:
    fixture = Path("tests/fixtures/openai_codex/model_list.json")
    raw = json.loads(fixture.read_text(encoding="utf-8"))
    response = parse_codex_response(ModelListResponse, raw, context="fixture")
    capabilities = CapabilitySet(models=tuple(normalize_models(response)))
    registry = ModelProfileRegistry.from_directory(default_profile_directory())

    enriched = CapabilityEnricher().enrich(
        capabilities, registry, evaluated_on=date(2026, 9, 18)
    )
    by_id = {model.id: model for model in enriched.models}

    assert set(by_id) == {
        "gpt-6-astra",
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "gpt-daybreak-blue-latest",
        "gpt-5.5",
    }
    assert {model_id for model_id, model in by_id.items() if model.relative_power} == {
        "gpt-6-astra",
        "gpt-5.6-luna",
    }
    assert all(model.effort_order is not None for model in by_id.values())
