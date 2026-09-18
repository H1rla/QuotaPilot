"""Pure, deterministic, provider-independent quota-aware routing."""

from __future__ import annotations

import math
from dataclasses import dataclass

from quotapilot.budget.models import BudgetReport
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.model import AIModel
from quotapilot.routing.errors import InvalidCapabilitiesError, NoRoutableModelError
from quotapilot.routing.models import (
    CandidateScore,
    MetadataSource,
    ProfileSource,
    QuotaPressureSource,
    RecommendationConfidence,
    RoutingPolicy,
    RoutingRecommendation,
    RoutingStep,
    TaskProfile,
)

_DIFFICULTY_WEIGHTS = {
    "complexity": 0.30,
    "ambiguity": 0.20,
    "failure_cost": 0.20,
    "low_verifiability": 0.15,
    "context_demand": 0.15,
}


@dataclass(frozen=True)
class _RoutableCandidate:
    model: AIModel
    score: CandidateScore


class RoutingEngine:
    """Recommend a first model/effort and advisory escalation path."""

    def __init__(self, policy: RoutingPolicy | None = None) -> None:
        self.policy = policy or RoutingPolicy()

    def recommend(
        self,
        task_profile: TaskProfile,
        budget_report: BudgetReport,
        capabilities: CapabilitySet,
    ) -> RoutingRecommendation:
        self._validate_capabilities(capabilities)
        warnings: list[str] = []

        difficulty = self._difficulty(task_profile)
        required_power = self._required_power(task_profile, difficulty)
        capability_floor = self._capability_floor(task_profile, required_power)
        pressure, pressure_source = self._quota_pressure(budget_report, warnings)

        scores, routable = self._score_candidates(
            capabilities.models,
            task_profile,
            pressure,
            required_power,
            capability_floor,
            warnings,
        )
        if not routable:
            raise NoRoutableModelError(
                "No routable model is available with sufficient capability metadata."
            )

        ranked = sorted(routable, key=self._ranking_key)
        selected = ranked[0]
        effort, effort_demand, quota_reduced = self._recommend_effort(
            selected.model, task_profile, pressure, warnings
        )
        escalation = self._escalation_path(
            selected.model,
            effort,
            task_profile,
            pressure,
            required_power,
            ranked,
            warnings,
        )
        alternatives = self._alternatives(
            selected.model, task_profile, pressure, ranked, warnings
        )
        explanation = self._explanation(
            task_profile,
            difficulty,
            required_power,
            capability_floor,
            pressure,
            pressure_source,
            selected,
            ranked,
            effort,
            quota_reduced,
            escalation,
        )

        return RoutingRecommendation(
            task_profile=task_profile,
            difficulty_score=difficulty,
            required_power=required_power,
            capability_floor=capability_floor,
            effort_demand=effort_demand,
            quota_pressure=pressure,
            quota_pressure_source=pressure_source,
            binding_pool_id=budget_report.binding_pool_id,
            selected_model_id=selected.model.id,
            selected_effort=effort,
            candidate_scores=tuple(sorted(scores, key=lambda score: score.model_id)),
            escalation_path=tuple(escalation),
            alternatives=tuple(alternatives),
            explanation=tuple(explanation),
            warnings=tuple(dict.fromkeys(warnings)),
            confidence=self._confidence(task_profile, pressure_source, selected, ranked),
        )

    @staticmethod
    def _difficulty(task: TaskProfile) -> float:
        return _clamp(
            _DIFFICULTY_WEIGHTS["complexity"] * task.complexity
            + _DIFFICULTY_WEIGHTS["ambiguity"] * task.ambiguity
            + _DIFFICULTY_WEIGHTS["failure_cost"] * task.failure_cost
            + _DIFFICULTY_WEIGHTS["low_verifiability"] * (1.0 - task.verifiability)
            + _DIFFICULTY_WEIGHTS["context_demand"] * task.context_demand
        )

    def _required_power(self, task: TaskProfile, difficulty: float) -> float:
        return _clamp(
            difficulty
            + self.policy.required_failure_weight * task.failure_cost
            + self.policy.required_low_verifiability_weight
            * (1.0 - task.verifiability)
        )

    def _capability_floor(self, task: TaskProfile, required_power: float) -> float:
        risk = (
            task.failure_cost + task.ambiguity + (1.0 - task.verifiability)
        ) / 3.0
        tolerance = max(
            0.0,
            self.policy.underpower_tolerance
            - self.policy.risk_tolerance_reduction * risk,
        )
        return max(0.0, required_power - tolerance)

    def _quota_pressure(
        self, report: BudgetReport, warnings: list[str]
    ) -> tuple[float, QuotaPressureSource]:
        if report.is_stale:
            warnings.append("budget_report_stale")
        warnings.extend(f"budget:{warning}" for warning in report.warnings)
        if report.effective_pressure is None:
            warnings.append("quota_pressure_unknown_using_neutral_fallback")
            return (
                self.policy.unknown_quota_pressure,
                QuotaPressureSource.FALLBACK_UNKNOWN,
            )
        return report.effective_pressure, QuotaPressureSource.BUDGET_REPORT

    def _score_candidates(
        self,
        models: tuple[AIModel, ...],
        task: TaskProfile,
        pressure: float,
        required_power: float,
        capability_floor: float,
        warnings: list[str],
    ) -> tuple[list[CandidateScore], list[_RoutableCandidate]]:
        scores: list[CandidateScore] = []
        routable: list[_RoutableCandidate] = []
        for model in models:
            if not model.selectable:
                scores.append(
                    CandidateScore(
                        model_id=model.id,
                        selectable=False,
                        relative_power=self._valid_metric(model.relative_power),
                        relative_cost=self._valid_metric(model.relative_cost),
                        relative_latency=self._valid_metric(model.relative_latency),
                        eligible=False,
                        rejection_reason="model_not_selectable",
                    )
                )
                continue

            power = self._valid_metric(model.relative_power)
            if power is None:
                reason = (
                    "missing_relative_power"
                    if model.relative_power is None
                    else "invalid_relative_power"
                )
                warnings.append(f"model:{model.id}:{reason}")
                scores.append(
                    CandidateScore(
                        model_id=model.id,
                        selectable=True,
                        relative_power=power,
                        relative_cost=self._valid_metric(model.relative_cost),
                        relative_latency=self._valid_metric(model.relative_latency),
                        eligible=False,
                        rejection_reason=reason,
                    )
                )
                continue

            cost, cost_source = self._metric_or_fallback(
                model.relative_cost,
                self.policy.missing_cost_fallback,
                model.id,
                "cost",
                warnings,
            )
            latency, latency_source = self._metric_or_fallback(
                model.relative_latency,
                self.policy.missing_latency_fallback,
                model.id,
                "latency",
                warnings,
            )
            if power < capability_floor:
                score = CandidateScore(
                    model_id=model.id,
                    selectable=True,
                    relative_power=power,
                    relative_cost=self._valid_metric(model.relative_cost),
                    relative_latency=self._valid_metric(model.relative_latency),
                    effective_cost=cost,
                    effective_latency=latency,
                    cost_source=cost_source,
                    latency_source=latency_source,
                    eligible=False,
                    rejection_reason="below_capability_floor",
                )
                scores.append(score)
                continue

            if power < required_power:
                quality = max(0.0, 1.0 - 2.0 * (required_power - power))
            else:
                quality = max(0.0, 1.0 - 0.35 * (power - required_power))
            quota_penalty = pressure * cost * self.policy.quota_pressure_weight
            latency_penalty = (
                task.latency_sensitivity * latency * self.policy.latency_weight
            )
            overcapability_penalty = (
                max(0.0, power - required_power)
                * self.policy.overcapability_weight
            )
            utility = quality - quota_penalty - latency_penalty - overcapability_penalty
            score = CandidateScore(
                model_id=model.id,
                selectable=True,
                relative_power=power,
                relative_cost=self._valid_metric(model.relative_cost),
                relative_latency=self._valid_metric(model.relative_latency),
                effective_cost=cost,
                effective_latency=latency,
                cost_source=cost_source,
                latency_source=latency_source,
                quality_score=quality,
                quota_penalty=quota_penalty,
                latency_penalty=latency_penalty,
                overcapability_penalty=overcapability_penalty,
                utility=utility,
                eligible=True,
            )
            scores.append(score)
            routable.append(_RoutableCandidate(model, score))
        return scores, routable

    @staticmethod
    def _valid_metric(value: float | None) -> float | None:
        if value is None or not math.isfinite(value) or not 0.0 <= value <= 1.0:
            return None
        return value

    def _metric_or_fallback(
        self,
        value: float | None,
        fallback: float,
        model_id: str,
        metric: str,
        warnings: list[str],
    ) -> tuple[float, MetadataSource]:
        valid = self._valid_metric(value)
        if valid is not None:
            return valid, MetadataSource.CAPABILITY
        warnings.append(f"model:{model_id}:{metric}_unknown_using_neutral_fallback")
        return fallback, MetadataSource.FALLBACK_NEUTRAL

    @staticmethod
    def _ranking_key(candidate: _RoutableCandidate) -> tuple[float, float, float, str]:
        score = candidate.score
        assert score.utility is not None
        assert score.effective_cost is not None
        assert score.effective_latency is not None
        return (
            -score.utility,
            score.effective_cost,
            score.effective_latency,
            candidate.model.id,
        )

    def _effort_demand(self, task: TaskProfile, pressure: float) -> tuple[float, bool]:
        demand = _clamp(
            0.35 * task.complexity
            + 0.25 * task.ambiguity
            + 0.20 * task.failure_cost
            + 0.20 * (1.0 - task.verifiability)
        )
        safe_to_reduce = (
            pressure >= 0.70
            and task.failure_cost < 0.50
            and task.ambiguity < 0.50
            and task.verifiability >= 0.70
        )
        if not safe_to_reduce:
            return demand, False
        reduction = (
            self.policy.effort_quota_reduction
            * pressure
            * task.verifiability
            * (1.0 - task.failure_cost)
            * (1.0 - task.ambiguity)
        )
        return max(0.0, demand - reduction), reduction > 0.0

    def _recommend_effort(
        self,
        model: AIModel,
        task: TaskProfile,
        pressure: float,
        warnings: list[str],
    ) -> tuple[str | None, float, bool]:
        demand, reduced = self._effort_demand(task, pressure)
        if not model.supported_efforts:
            warnings.append(f"model:{model.id}:no_effort_catalog")
            return None, demand, reduced
        if model.effort_order is None:
            warnings.append(f"model:{model.id}:effort_order_unknown")
            return None, demand, reduced
        index = min(len(model.effort_order) - 1, int(demand * len(model.effort_order)))
        return model.effort_order[index], demand, reduced

    def _escalation_path(
        self,
        selected: AIModel,
        selected_effort: str | None,
        task: TaskProfile,
        pressure: float,
        required_power: float,
        ranked: list[_RoutableCandidate],
        warnings: list[str],
    ) -> list[RoutingStep]:
        if not self.policy.escalation_enabled or self.policy.max_escalation_steps == 0:
            return []

        steps: list[RoutingStep] = []

        def add(model: AIModel, effort: str | None, reason: str) -> None:
            step = RoutingStep(model_id=model.id, effort=effort, reason=reason)
            if not steps or (steps[-1].model_id, steps[-1].effort) != (
                step.model_id,
                step.effort,
            ):
                steps.append(step)

        same_model_higher = self._next_effort(selected, selected_effort)
        stronger = sorted(
            (
                candidate
                for candidate in ranked
                if candidate.model.relative_power is not None
                and selected.relative_power is not None
                and candidate.model.relative_power > selected.relative_power
            ),
            key=lambda candidate: (candidate.model.relative_power or 0.0, candidate.model.id),
        )

        # A model still below target should gain capability before spending more effort.
        model_first = (
            selected.relative_power is not None
            and selected.relative_power < required_power
            and bool(stronger)
        )
        if same_model_higher is not None and not model_first:
            add(selected, same_model_higher, "increase effort on the selected model")

        if stronger:
            next_model = stronger[0].model
            next_effort, _, _ = self._recommend_effort(
                next_model, task, pressure, warnings
            )
            add(next_model, next_effort, "move to the next stronger routable model")
            next_model_higher = self._next_effort(next_model, next_effort)
            if next_model_higher is not None:
                add(next_model, next_model_higher, "increase effort on the stronger model")

        return steps[: self.policy.max_escalation_steps]

    @staticmethod
    def _next_effort(model: AIModel, effort: str | None) -> str | None:
        if model.effort_order is None or effort is None:
            return None
        index = model.effort_order.index(effort)
        if index + 1 >= len(model.effort_order):
            return None
        return model.effort_order[index + 1]

    def _alternatives(
        self,
        selected: AIModel,
        task: TaskProfile,
        pressure: float,
        ranked: list[_RoutableCandidate],
        warnings: list[str],
    ) -> list[RoutingStep]:
        if self.policy.max_alternatives == 0:
            return []
        others = [candidate for candidate in ranked if candidate.model.id != selected.id]
        chosen: list[_RoutableCandidate] = []

        selected_score = next(
            candidate.score for candidate in ranked if candidate.model.id == selected.id
        )
        cheaper = [
            candidate
            for candidate in others
            if candidate.score.effective_cost is not None
            and selected_score.effective_cost is not None
            and candidate.score.effective_cost < selected_score.effective_cost
        ]
        stronger = [
            candidate
            for candidate in others
            if candidate.model.relative_power is not None
            and selected.relative_power is not None
            and candidate.model.relative_power > selected.relative_power
        ]
        for group in (cheaper, stronger, others):
            for candidate in group:
                if candidate not in chosen:
                    chosen.append(candidate)
                if len(chosen) >= self.policy.max_alternatives:
                    break
            if len(chosen) >= self.policy.max_alternatives:
                break

        result: list[RoutingStep] = []
        for candidate in chosen:
            effort, _, _ = self._recommend_effort(
                candidate.model, task, pressure, warnings
            )
            result.append(
                RoutingStep(
                    model_id=candidate.model.id,
                    effort=effort,
                    reason="next-best eligible utility with a distinct cost/capability tradeoff",
                )
            )
        return result

    @staticmethod
    def _explanation(
        task: TaskProfile,
        difficulty: float,
        required_power: float,
        capability_floor: float,
        pressure: float,
        pressure_source: QuotaPressureSource,
        selected: _RoutableCandidate,
        ranked: list[_RoutableCandidate],
        effort: str | None,
        quota_reduced: bool,
        escalation: list[RoutingStep],
    ) -> list[str]:
        explanations = [
            f"Task difficulty is {difficulty:.3f}; required model power is {required_power:.3f}.",
            (
                f"Risk inputs are failure_cost={task.failure_cost:.3f}, "
                f"ambiguity={task.ambiguity:.3f}, and verifiability={task.verifiability:.3f}."
            ),
            (
                f"Quota pressure {pressure:.3f} ({pressure_source.value}) contributed "
                f"a {selected.score.quota_penalty:.3f} cost penalty."
            ),
            (
                f"{selected.model.id} meets the capability floor {capability_floor:.3f} "
                "and has the highest policy utility."
            ),
        ]
        weaker = [
            candidate
            for candidate in ranked
            if candidate.model.relative_power is not None
            and selected.model.relative_power is not None
            and candidate.model.relative_power < selected.model.relative_power
        ]
        stronger = [
            candidate
            for candidate in ranked
            if candidate.model.relative_power is not None
            and selected.model.relative_power is not None
            and candidate.model.relative_power > selected.model.relative_power
        ]
        explanations.append(
            "Weaker eligible models scored lower after capability-fit and policy penalties."
            if weaker
            else "No weaker model was both selectable and above the capability floor."
        )
        explanations.append(
            "Stronger eligible models offered less utility after over-capability, "
            "quota, and latency penalties."
            if stronger
            else "No stronger routable model was available."
        )
        if effort is None:
            explanations.append(
                "No effort was selected because no explicit ordered effort catalog "
                "was available."
            )
        elif quota_reduced:
            explanations.append(
                f"Effort {effort} was selected after a quota-saving reduction allowed "
                "by low task risk and high verifiability."
            )
        else:
            explanations.append(
                f"Effort {effort} was selected from the model's explicit ordered effort catalog."
            )
        explanations.append(
            f"The advisory escalation path contains {len(escalation)} step(s) and "
            "performs no execution."
        )
        return explanations

    @staticmethod
    def _confidence(
        task: TaskProfile,
        pressure_source: QuotaPressureSource,
        selected: _RoutableCandidate,
        ranked: list[_RoutableCandidate],
    ) -> RecommendationConfidence:
        if pressure_source is QuotaPressureSource.FALLBACK_UNKNOWN:
            return RecommendationConfidence.LOW
        if (
            selected.score.cost_source is MetadataSource.FALLBACK_NEUTRAL
            or selected.score.latency_source is MetadataSource.FALLBACK_NEUTRAL
        ):
            return RecommendationConfidence.LOW
        if len(ranked) > 1:
            first = selected.score.utility
            second = ranked[1].score.utility
            if first is not None and second is not None and first - second < 0.03:
                return RecommendationConfidence.LOW
        if task.profile_source is ProfileSource.EXPLICIT:
            return RecommendationConfidence.HIGH
        return RecommendationConfidence.MEDIUM

    @staticmethod
    def _validate_capabilities(capabilities: CapabilitySet) -> None:
        ids = [model.id for model in capabilities.models]
        if len(ids) != len(set(ids)):
            raise InvalidCapabilitiesError("CapabilitySet contains duplicate model IDs.")


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))
