"""Scenario coverage, deterministic replay, and violation-detector tests."""

from __future__ import annotations

from quotapilot.budget.models import BudgetState
from quotapilot.calibration import (
    ScenarioEvaluator,
    ViolationKind,
    default_calibration_path,
    load_calibration_suite,
)
from quotapilot.routing.models import QuotaPressureSource


def test_initial_suite_covers_required_tasks_and_quota_states() -> None:
    suite = load_calibration_suite(default_calibration_path())

    assert len(suite.scenarios) == 10
    assert {scenario.quota_state for scenario in suite.scenarios} >= {
        BudgetState.VERY_UNDER,
        BudgetState.ON_TRACK,
        BudgetState.OVER,
        BudgetState.CRITICAL,
        BudgetState.UNKNOWN,
    }
    assert {scenario.scenario_id for scenario in suite.scenarios} == {
        "trivial-typo-very-under",
        "small-deterministic-refactor-on-track",
        "bounded-implementation-over",
        "test-writing-critical",
        "local-debugging-on-track",
        "complex-debugging-over",
        "repository-wide-critical",
        "architecture-critical",
        "research-review-unknown",
        "high-failure-low-verifiability-critical",
    }


def test_initial_suite_passes_all_component_metrics_deterministically() -> None:
    suite = load_calibration_suite(default_calibration_path())
    evaluator = ScenarioEvaluator()

    first = evaluator.evaluate(suite)
    second = evaluator.evaluate(suite)

    assert first == second
    assert first.passed is True
    assert first.metrics.scenario_count == 10
    assert first.metrics.acceptable_hits == 10
    assert first.metrics.unacceptable_recommendations == 0
    assert first.metrics.capability_floor_violations == 0
    assert first.metrics.anti_waste_violations == 0
    assert first.metrics.unknown_quota_violations == 0
    assert first.metrics.unsupported_effort_violations == 0
    assert first.metrics.non_selectable_model_violations == 0
    assert first.metrics.determinism_violations == 0


def _recommendation(scenario_id: str):
    suite = load_calibration_suite(default_calibration_path())
    scenario = next(item for item in suite.scenarios if item.scenario_id == scenario_id)
    evaluator = ScenarioEvaluator()
    recommendation = evaluator.engine.recommend(
        scenario.task.to_task_profile(), scenario.budget_report(), suite.capabilities()
    )
    return evaluator, suite, scenario, recommendation


def _kinds(violations) -> set[ViolationKind]:
    return {violation.kind for violation in violations}


def test_anti_waste_violation_is_detected() -> None:
    evaluator, suite, scenario, recommendation = _recommendation(
        "trivial-typo-very-under"
    )
    bad = recommendation.model_copy(
        update={"selected_model_id": "calibration-strong", "selected_effort": "medium"}
    )

    violations = evaluator.inspect_recommendation(
        scenario, bad, bad, suite.capabilities()
    )

    assert ViolationKind.ANTI_WASTE in _kinds(violations)
    assert ViolationKind.UNACCEPTABLE_RECOMMENDATION in _kinds(violations)


def test_model_outside_acceptable_set_is_counted_as_unacceptable() -> None:
    evaluator, suite, scenario, recommendation = _recommendation(
        "small-deterministic-refactor-on-track"
    )
    bad = recommendation.model_copy(
        update={"selected_model_id": "calibration-strong", "selected_effort": "medium"}
    )

    violations = evaluator.inspect_recommendation(
        scenario, bad, bad, suite.capabilities()
    )

    assert ViolationKind.UNACCEPTABLE_RECOMMENDATION in _kinds(violations)


def test_capability_floor_violation_is_detected() -> None:
    evaluator, suite, scenario, recommendation = _recommendation(
        "architecture-critical"
    )
    bad = recommendation.model_copy(
        update={"selected_model_id": "calibration-light", "selected_effort": "medium"}
    )

    violations = evaluator.inspect_recommendation(
        scenario, bad, bad, suite.capabilities()
    )

    assert ViolationKind.CAPABILITY_FLOOR in _kinds(violations)


def test_unknown_quota_misuse_is_detected() -> None:
    evaluator, suite, scenario, recommendation = _recommendation(
        "research-review-unknown"
    )
    bad = recommendation.model_copy(
        update={
            "quota_pressure": 0.0,
            "quota_pressure_source": QuotaPressureSource.BUDGET_REPORT,
        }
    )

    violations = evaluator.inspect_recommendation(
        scenario, bad, bad, suite.capabilities()
    )

    assert ViolationKind.UNKNOWN_QUOTA in _kinds(violations)


def test_unsupported_effort_and_nonselectable_model_are_detected() -> None:
    evaluator, suite, scenario, recommendation = _recommendation(
        "bounded-implementation-over"
    )
    unsupported = recommendation.model_copy(update={"selected_effort": "impossible"})
    hidden = recommendation.model_copy(
        update={"selected_model_id": "calibration-hidden", "selected_effort": "max"}
    )

    unsupported_violations = evaluator.inspect_recommendation(
        scenario, unsupported, unsupported, suite.capabilities()
    )
    hidden_violations = evaluator.inspect_recommendation(
        scenario, hidden, hidden, suite.capabilities()
    )

    assert ViolationKind.UNSUPPORTED_EFFORT in _kinds(unsupported_violations)
    assert ViolationKind.NON_SELECTABLE_MODEL in _kinds(hidden_violations)


def test_determinism_violation_is_detected() -> None:
    evaluator, suite, scenario, recommendation = _recommendation(
        "bounded-implementation-over"
    )
    changed = recommendation.model_copy(update={"warnings": ("changed",)})

    violations = evaluator.inspect_recommendation(
        scenario, recommendation, changed, suite.capabilities()
    )

    assert ViolationKind.DETERMINISM in _kinds(violations)
