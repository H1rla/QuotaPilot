"""Deterministic replay through the existing Routing Engine."""

from __future__ import annotations

from collections import Counter

from quotapilot.calibration.models import (
    CalibrationMetrics,
    CalibrationReport,
    CalibrationScenario,
    CalibrationSuite,
    CalibrationViolation,
    ScenarioOutcome,
    ViolationKind,
)
from quotapilot.domain.capability import CapabilitySet
from quotapilot.routing.engine import RoutingEngine
from quotapilot.routing.errors import NoRoutableModelError
from quotapilot.routing.models import (
    QuotaPressureSource,
    RoutingRecommendation,
)


class ScenarioEvaluator:
    """Replay explicit scenarios; never tunes or mutates routing policy."""

    def __init__(self, engine: RoutingEngine | None = None) -> None:
        self.engine = engine or RoutingEngine()

    def evaluate(self, suite: CalibrationSuite) -> CalibrationReport:
        capabilities = suite.capabilities()
        outcomes: list[ScenarioOutcome] = []
        all_violations: list[CalibrationViolation] = []

        for scenario in suite.scenarios:
            try:
                recommendation = self.engine.recommend(
                    scenario.task.to_task_profile(),
                    scenario.budget_report(),
                    capabilities,
                )
                repeated = self.engine.recommend(
                    scenario.task.to_task_profile(),
                    scenario.budget_report(),
                    capabilities,
                )
            except NoRoutableModelError:
                violation = CalibrationViolation(
                    scenario_id=scenario.scenario_id,
                    kind=ViolationKind.NO_RECOMMENDATION,
                    detail="scenario produced no routable recommendation",
                )
                outcome = ScenarioOutcome(
                    scenario_id=scenario.scenario_id,
                    selected_model_id=None,
                    selected_effort=None,
                    acceptable_hit=False,
                    violations=(violation,),
                )
            else:
                violations = self.inspect_recommendation(
                    scenario,
                    recommendation,
                    repeated,
                    capabilities,
                )
                outcome = ScenarioOutcome(
                    scenario_id=scenario.scenario_id,
                    selected_model_id=recommendation.selected_model_id,
                    selected_effort=recommendation.selected_effort,
                    acceptable_hit=(
                        recommendation.selected_model_id
                        in scenario.acceptable_models
                    ),
                    violations=violations,
                )
            outcomes.append(outcome)
            all_violations.extend(outcome.violations)

        counts = Counter(violation.kind for violation in all_violations)
        metrics = CalibrationMetrics(
            scenario_count=len(suite.scenarios),
            acceptable_hits=sum(outcome.acceptable_hit for outcome in outcomes),
            unacceptable_recommendations=counts[
                ViolationKind.UNACCEPTABLE_RECOMMENDATION
            ],
            capability_floor_violations=counts[ViolationKind.CAPABILITY_FLOOR],
            anti_waste_violations=counts[ViolationKind.ANTI_WASTE],
            unknown_quota_violations=counts[ViolationKind.UNKNOWN_QUOTA],
            unsupported_effort_violations=counts[ViolationKind.UNSUPPORTED_EFFORT],
            non_selectable_model_violations=counts[ViolationKind.NON_SELECTABLE_MODEL],
            determinism_violations=counts[ViolationKind.DETERMINISM],
            routing_failures=counts[ViolationKind.NO_RECOMMENDATION],
        )
        return CalibrationReport(
            capability_profile_version=suite.capability_profile_version,
            metrics=metrics,
            outcomes=tuple(outcomes),
            violations=tuple(all_violations),
            passed=(not all_violations and metrics.acceptable_hits == metrics.scenario_count),
        )

    def inspect_recommendation(
        self,
        scenario: CalibrationScenario,
        recommendation: RoutingRecommendation,
        repeated: RoutingRecommendation,
        capabilities: CapabilitySet,
    ) -> tuple[CalibrationViolation, ...]:
        """Check one result, exposed so regression tests can inject bad outputs."""
        violations: list[CalibrationViolation] = []

        def add(kind: ViolationKind, detail: str) -> None:
            violations.append(
                CalibrationViolation(
                    scenario_id=scenario.scenario_id,
                    kind=kind,
                    detail=detail,
                )
            )

        models = {model.id: model for model in capabilities.models}
        selected = models.get(recommendation.selected_model_id)
        if selected is None or not selected.selectable:
            add(
                ViolationKind.NON_SELECTABLE_MODEL,
                "selected model is absent or non-selectable",
            )
        else:
            if (
                selected.relative_power is None
                or selected.relative_power < recommendation.capability_floor
            ):
                add(
                    ViolationKind.CAPABILITY_FLOOR,
                    "selected model is below the recommendation capability floor",
                )
            if (
                recommendation.selected_effort is not None
                and recommendation.selected_effort not in selected.supported_efforts
            ):
                add(
                    ViolationKind.UNSUPPORTED_EFFORT,
                    "selected effort is not supported by the selected model",
                )

        if recommendation.selected_model_id not in scenario.acceptable_models:
            detail = (
                "selected model is explicitly unacceptable for this scenario"
                if recommendation.selected_model_id in scenario.unacceptable_models
                else "selected model is outside this scenario's acceptable set"
            )
            add(
                ViolationKind.UNACCEPTABLE_RECOMMENDATION,
                detail,
            )

        if scenario.anti_waste_guard and selected is not None:
            eligible_powers = [
                score.relative_power
                for score in recommendation.candidate_scores
                if score.eligible and score.relative_power is not None
            ]
            lower_eligible = any(
                power < selected.relative_power
                for power in eligible_powers
                if selected.relative_power is not None
            )
            strongest = max(eligible_powers, default=None)
            if (
                selected.relative_power is not None
                and strongest == selected.relative_power
                and lower_eligible
            ):
                add(
                    ViolationKind.ANTI_WASTE,
                    "strongest eligible model was selected despite a lower eligible model",
                )

        if scenario.quota_pressure is None and (
            recommendation.quota_pressure_source
            is not QuotaPressureSource.FALLBACK_UNKNOWN
            or recommendation.quota_pressure != self.engine.policy.unknown_quota_pressure
        ):
            add(
                ViolationKind.UNKNOWN_QUOTA,
                "UNKNOWN quota did not use the explicit neutral fallback",
            )

        if recommendation != repeated:
            add(ViolationKind.DETERMINISM, "identical replay produced a different result")
        return tuple(violations)
