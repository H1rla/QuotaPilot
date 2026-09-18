"""Pure Routing Engine behavior, safety, and determinism tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from quotapilot.budget.models import BudgetReport
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.model import AIModel
from quotapilot.routing.engine import RoutingEngine
from quotapilot.routing.errors import InvalidCapabilitiesError, NoRoutableModelError
from quotapilot.routing.models import (
    MetadataSource,
    ProfileSource,
    QuotaPressureSource,
    RoutingPolicy,
    TaskClass,
    TaskProfile,
)

NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)


def _budget(
    pressure: float | None,
    *,
    stale: bool = False,
    warnings: tuple[str, ...] = (),
) -> BudgetReport:
    return BudgetReport(
        captured_at=NOW,
        evaluated_at=NOW,
        snapshot_age_seconds=0.0,
        is_stale=stale,
        reserve_fraction=0.1,
        timezone="UTC",
        pools=(),
        effective_pressure=pressure,
        binding_pool_id="weekly" if pressure is not None else None,
        warnings=warnings,
    )


def _task(
    *,
    complexity: float = 0.5,
    ambiguity: float = 0.4,
    failure_cost: float = 0.4,
    verifiability: float = 0.6,
    context_demand: float = 0.5,
    latency_sensitivity: float = 0.3,
) -> TaskProfile:
    return TaskProfile(
        summary="Synthetic provider-independent task",
        complexity=complexity,
        ambiguity=ambiguity,
        failure_cost=failure_cost,
        verifiability=verifiability,
        context_demand=context_demand,
        latency_sensitivity=latency_sensitivity,
        task_class=TaskClass.UNKNOWN,
        profile_source=ProfileSource.EXPLICIT,
    )


def _model(
    model_id: str,
    power: float | None,
    cost: float | None,
    latency: float | None,
    *,
    selectable: bool = True,
    efforts: tuple[str, ...] = ("brief", "normal", "deep"),
    ordered: bool = True,
) -> AIModel:
    return AIModel(
        id=model_id,
        provider="test-provider",
        selectable=selectable,
        supported_efforts=efforts,
        effort_order=efforts if ordered else None,
        relative_power=power,
        relative_cost=cost,
        relative_latency=latency,
    )


def _capabilities(*models: AIModel) -> CapabilitySet:
    return CapabilitySet(models=models, supports_model_selection=len(models) > 1)


def _standard_models() -> tuple[AIModel, ...]:
    return (
        _model("light", 0.30, 0.10, 0.10),
        _model("balanced", 0.65, 0.50, 0.40),
        _model("strong", 0.95, 0.90, 0.80),
    )


@pytest.mark.parametrize("pressure", [0.0, 0.15, 0.35, 0.70, 1.0])
def test_all_known_quota_pressure_levels_are_consumed(pressure: float) -> None:
    result = RoutingEngine().recommend(
        _task(), _budget(pressure), _capabilities(*_standard_models())
    )

    assert result.quota_pressure == pressure
    assert result.quota_pressure_source is QuotaPressureSource.BUDGET_REPORT


def test_unknown_quota_uses_explicit_neutral_fallback() -> None:
    result = RoutingEngine(RoutingPolicy(unknown_quota_pressure=0.42)).recommend(
        _task(), _budget(None), _capabilities(*_standard_models())
    )

    assert result.quota_pressure == 0.42
    assert result.quota_pressure_source is QuotaPressureSource.FALLBACK_UNKNOWN
    assert "quota_pressure_unknown_using_neutral_fallback" in result.warnings


def test_one_candidate_is_selected_and_effort_is_supported() -> None:
    model = _model("only", 0.7, 0.4, 0.3)

    result = RoutingEngine().recommend(_task(), _budget(0.35), _capabilities(model))

    assert result.selected_model_id == "only"
    assert result.selected_effort in model.supported_efforts


def test_unknown_and_nonselectable_models_are_preserved_but_excluded() -> None:
    models = (
        _model("hidden", 1.0, 0.1, 0.1, selectable=False),
        _model("future", None, None, None),
        _model("routeable", 0.7, 0.4, 0.4),
    )

    result = RoutingEngine().recommend(_task(), _budget(0.35), _capabilities(*models))
    by_id = {score.model_id: score for score in result.candidate_scores}

    assert result.selected_model_id == "routeable"
    assert by_id["hidden"].rejection_reason == "model_not_selectable"
    assert by_id["future"].rejection_reason == "missing_relative_power"


def test_no_routable_candidate_is_a_typed_failure() -> None:
    capabilities = _capabilities(
        _model("hidden", 0.9, 0.2, 0.2, selectable=False),
        _model("unknown", None, None, None),
    )

    with pytest.raises(NoRoutableModelError, match="No routable model"):
        RoutingEngine().recommend(_task(), _budget(0.35), capabilities)


def test_missing_cost_and_latency_use_neutral_not_zero() -> None:
    result = RoutingEngine(
        RoutingPolicy(missing_cost_fallback=0.4, missing_latency_fallback=0.6)
    ).recommend(_task(), _budget(0.5), _capabilities(_model("partial", 0.7, None, None)))
    score = result.candidate_scores[0]

    assert score.effective_cost == 0.4
    assert score.effective_latency == 0.6
    assert score.cost_source is MetadataSource.FALLBACK_NEUTRAL
    assert score.latency_source is MetadataSource.FALLBACK_NEUTRAL


def test_equal_utility_tie_uses_model_id_after_cost_and_latency() -> None:
    models = (
        _model("z-model", 0.7, 0.4, 0.4),
        _model("a-model", 0.7, 0.4, 0.4),
    )

    result = RoutingEngine().recommend(_task(), _budget(0.5), _capabilities(*models))

    assert result.selected_model_id == "a-model"


def test_very_under_trivial_task_does_not_choose_strongest_model() -> None:
    task = _task(
        complexity=0.1,
        ambiguity=0.1,
        failure_cost=0.1,
        verifiability=0.95,
        context_demand=0.1,
        latency_sensitivity=0.8,
    )

    result = RoutingEngine().recommend(
        task, _budget(0.0), _capabilities(*_standard_models())
    )

    assert result.selected_model_id == "light"


def test_critical_quota_cannot_bypass_hard_task_capability_floor() -> None:
    task = _task(
        complexity=0.95,
        ambiguity=0.85,
        failure_cost=0.95,
        verifiability=0.10,
        context_demand=0.95,
        latency_sensitivity=0.1,
    )

    result = RoutingEngine().recommend(
        task, _budget(1.0), _capabilities(*_standard_models())
    )

    assert result.selected_model_id == "strong"
    selected = next(
        score for score in result.candidate_scores if score.model_id == "strong"
    )
    assert selected.relative_power is not None
    assert selected.relative_power >= result.capability_floor
    assert all(
        score.rejection_reason == "below_capability_floor"
        for score in result.candidate_scores
        if score.model_id != "strong"
    )


def test_higher_pressure_can_choose_cheaper_without_crossing_floor() -> None:
    task = _task(
        complexity=0.6,
        ambiguity=0.6,
        failure_cost=0.5,
        verifiability=0.4,
        context_demand=0.7,
        latency_sensitivity=0.1,
    )
    models = _capabilities(
        _model("cheap", 0.65, 0.05, 0.2),
        _model("expensive", 0.80, 1.0, 0.2),
    )

    low_pressure = RoutingEngine().recommend(task, _budget(0.0), models)
    high_pressure = RoutingEngine().recommend(task, _budget(1.0), models)

    assert low_pressure.selected_model_id == "expensive"
    assert high_pressure.selected_model_id == "cheap"
    assert all(
        score.relative_power is None
        or not score.eligible
        or score.relative_power >= high_pressure.capability_floor
        for score in high_pressure.candidate_scores
    )


def test_effort_requires_explicit_capability_order() -> None:
    model = _model("unordered", 0.8, 0.4, 0.4, ordered=False)

    result = RoutingEngine().recommend(_task(), _budget(0.3), _capabilities(model))

    assert result.selected_effort is None
    assert "model:unordered:effort_order_unknown" in result.warnings


def test_empty_and_single_effort_catalogs_are_safe() -> None:
    empty = _model("empty", 0.8, 0.4, 0.4, efforts=())
    one = _model("one", 0.8, 0.4, 0.4, efforts=("provider-default",))

    empty_result = RoutingEngine().recommend(_task(), _budget(0.3), _capabilities(empty))
    one_result = RoutingEngine().recommend(_task(), _budget(0.3), _capabilities(one))

    assert empty_result.selected_effort is None
    assert one_result.selected_effort == "provider-default"


def test_high_pressure_reduces_effort_only_for_low_risk_verifiable_task() -> None:
    model = _model("candidate", 1.0, 0.4, 0.4)
    low_risk = _task(
        complexity=0.6,
        ambiguity=0.2,
        failure_cost=0.2,
        verifiability=0.9,
        context_demand=0.5,
    )
    high_risk = _task(
        complexity=0.6,
        ambiguity=0.8,
        failure_cost=0.9,
        verifiability=0.1,
        context_demand=0.5,
    )

    low_pressure = RoutingEngine().recommend(
        low_risk, _budget(0.0), _capabilities(model)
    )
    high_pressure = RoutingEngine().recommend(
        low_risk, _budget(1.0), _capabilities(model)
    )
    risky = RoutingEngine().recommend(high_risk, _budget(1.0), _capabilities(model))

    assert model.effort_order is not None
    high_index = model.effort_order.index(high_pressure.selected_effort or "")
    low_index = model.effort_order.index(low_pressure.selected_effort or "")
    assert high_index <= low_index
    assert risky.selected_effort == "deep"


def test_escalation_uses_supported_efforts_and_stronger_models_without_duplicates() -> None:
    result = RoutingEngine().recommend(
        _task(), _budget(0.35), _capabilities(*_standard_models())
    )
    models = {model.id: model for model in _standard_models()}
    pairs = [(step.model_id, step.effort) for step in result.escalation_path]

    assert len(pairs) == len(set(pairs))
    powers = [models[step.model_id].relative_power for step in result.escalation_path]
    known_powers = [power for power in powers if power is not None]
    assert len(known_powers) == len(powers)
    assert known_powers == sorted(known_powers)
    for step in result.escalation_path:
        assert models[step.model_id].selectable
        assert step.effort is None or step.effort in models[step.model_id].supported_efforts


def test_escalation_can_be_disabled() -> None:
    result = RoutingEngine(RoutingPolicy(escalation_enabled=False)).recommend(
        _task(), _budget(0.35), _capabilities(*_standard_models())
    )

    assert result.escalation_path == ()


def test_escalation_prefers_higher_effort_on_adequate_selected_model() -> None:
    selected = _model("selected", 0.7, 0.3, 0.3)
    stronger = _model("stronger", 0.9, 0.8, 0.7)

    result = RoutingEngine().recommend(
        _task(complexity=0.4, ambiguity=0.3, failure_cost=0.3),
        _budget(0.3),
        _capabilities(selected, stronger),
    )

    assert result.selected_model_id == "selected"
    assert result.escalation_path
    first = result.escalation_path[0]
    assert first.model_id == "selected"
    assert selected.effort_order is not None
    assert selected.effort_order.index(first.effort or "") > selected.effort_order.index(
        result.selected_effort or ""
    )


def test_strongest_highest_effort_has_empty_escalation() -> None:
    strongest = _model("strongest", 1.0, 0.8, 0.8, efforts=("only",))

    result = RoutingEngine().recommend(
        _task(complexity=1.0, failure_cost=1.0, verifiability=0.0),
        _budget(0.2),
        _capabilities(strongest),
    )

    assert result.escalation_path == ()


def test_stale_budget_and_budget_warnings_are_visible() -> None:
    result = RoutingEngine().recommend(
        _task(),
        _budget(0.3, stale=True, warnings=("future_captured_at",)),
        _capabilities(_model("candidate", 0.8, 0.4, 0.4)),
    )

    assert "budget_report_stale" in result.warnings
    assert "budget:future_captured_at" in result.warnings


def test_same_inputs_produce_identical_recommendations() -> None:
    engine = RoutingEngine()
    task = _task()
    budget = _budget(0.7)
    capabilities = _capabilities(*_standard_models())

    assert engine.recommend(task, budget, capabilities) == engine.recommend(
        task, budget, capabilities
    )


def test_required_power_is_monotonic_for_complexity_and_failure_cost() -> None:
    engine = RoutingEngine()
    capabilities = _capabilities(*_standard_models())
    base = engine.recommend(_task(), _budget(0.3), capabilities)
    complex_result = engine.recommend(
        _task(complexity=0.8), _budget(0.3), capabilities
    )
    risky_result = engine.recommend(
        _task(failure_cost=0.8), _budget(0.3), capabilities
    )

    assert complex_result.required_power >= base.required_power
    assert risky_result.required_power >= base.required_power


def test_selected_model_and_effort_always_come_from_capabilities() -> None:
    capabilities = _capabilities(*_standard_models())
    result = RoutingEngine().recommend(_task(), _budget(0.7), capabilities)
    selected = next(
        model for model in capabilities.models if model.id == result.selected_model_id
    )

    assert selected.selectable
    assert result.selected_effort in selected.supported_efforts
    assert 0.0 <= result.required_power <= 1.0
    assert 0.0 <= result.quota_pressure <= 1.0


def test_alternatives_are_small_known_selectable_candidates() -> None:
    capabilities = _capabilities(*_standard_models())

    result = RoutingEngine(RoutingPolicy(max_alternatives=2)).recommend(
        _task(), _budget(0.4), capabilities
    )

    known = {model.id for model in capabilities.models if model.selectable}
    assert len(result.alternatives) <= 2
    assert all(step.model_id in known for step in result.alternatives)
    assert result.selected_model_id not in {step.model_id for step in result.alternatives}


def test_duplicate_model_ids_are_rejected() -> None:
    capabilities = _capabilities(
        _model("same", 0.7, 0.4, 0.4),
        _model("same", 0.8, 0.5, 0.5),
    )

    with pytest.raises(InvalidCapabilitiesError, match="duplicate model IDs"):
        RoutingEngine().recommend(_task(), _budget(0.3), capabilities)
