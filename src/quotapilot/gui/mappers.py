"""Pure privacy-safe conversion from core models into QML-ready values."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from quotapilot.budget.forecast import DailyForecast
from quotapilot.budget.models import BudgetReport, PoolBudgetAssessment
from quotapilot.capabilities.models import ModelCapabilityView
from quotapilot.execution.models import ExecutionPlan, ExecutionResult
from quotapilot.observability.models import StatusPool, StatusReport
from quotapilot.providers.base import ProviderAuthentication, ProviderConnection
from quotapilot.routing.models import RoutingRecommendation
from quotapilot.services.provider_status import ProviderStatus

from .formatting import age, decimal, duration, fraction, timestamp

_EXPLANATION_PATTERNS = (
    (
        re.compile(r"^Task difficulty is (.+); required model power is (.+)\.$"),
        "Task difficulty is %1; required model power is %2.",
    ),
    (
        re.compile(
            r"^Risk inputs are failure_cost=(.+), ambiguity=(.+), and verifiability=(.+)\.$"
        ),
        "Risk inputs are failure_cost=%1, ambiguity=%2, and verifiability=%3.",
    ),
    (
        re.compile(r"^Quota pressure (.+) \((.+)\) contributed a (.+) cost penalty\.$"),
        "Quota pressure %1 (%2) contributed a %3 cost penalty.",
    ),
    (
        re.compile(r"^(.+) meets the capability floor (.+) and has the highest policy utility\.$"),
        "%1 meets the capability floor %2 and has the highest policy utility.",
    ),
    (
        re.compile(
            r"^Effort (.+) was selected after a quota-saving reduction allowed by "
            r"low task risk and high verifiability\.$"
        ),
        "Effort %1 was selected after a quota-saving reduction allowed by "
        "low task risk and high verifiability.",
    ),
    (
        re.compile(
            r"^Effort (.+) was selected from the model's explicit ordered effort catalog\.$"
        ),
        "Effort %1 was selected from the model's explicit ordered effort catalog.",
    ),
    (
        re.compile(
            r"^The advisory escalation path contains (.+) step\(s\) and performs no execution\.$"
        ),
        "The advisory escalation path contains %1 step(s) and performs no execution.",
    ),
)


def _map_explanation(source: str) -> dict[str, Any]:
    """Separate stable routing templates from values for Qt translation."""
    for pattern, template in _EXPLANATION_PATTERNS:
        match = pattern.fullmatch(source)
        if match is not None:
            return {"source": template, "args": list(match.groups())}
    return {"source": source, "args": []}


def _binding_pool(report: StatusReport) -> StatusPool | None:
    return next(
        (pool for pool in report.pools if pool.pool_id == report.binding_pool_id),
        report.pools[0] if report.pools else None,
    )


def map_overview(report: StatusReport | None) -> dict[str, Any]:
    if report is None:
        return {
            "available": False,
            "remaining": "Unknown",
            "reset": "Unknown",
            "state": "UNKNOWN",
            "todayBudget": "Unknown",
            "pressure": "Unknown",
            "routableModels": "Unknown",
            "profileFreshness": "Unknown",
            "freshness": "No persisted snapshot",
            "freshnessAge": "Unknown",
            "stale": False,
            "provider": "Unavailable",
            "errorAction": "Refresh",
        }
    pool = _binding_pool(report)
    state = pool.state.value.upper() if pool is not None else "UNKNOWN"
    reset_seconds = None
    if pool is not None and pool.resets_at is not None:
        reset_seconds = max(
            0,
            round((pool.resets_at - report.evaluated_at).total_seconds()),
        )
    freshness = f"Snapshot {age(report.snapshot_age_seconds)}"
    if report.is_stale:
        freshness += " · STALE"
    return {
        "available": True,
        "remaining": fraction(pool.remaining_fraction if pool else None, digits=0),
        "remainingValue": pool.remaining_fraction if pool else None,
        "usedValue": pool.used_fraction if pool else None,
        "reset": duration(reset_seconds),
        "state": state,
        "todayBudget": fraction(pool.today_budget_fraction if pool else None),
        "pressure": decimal(report.effective_pressure),
        "pressureValue": report.effective_pressure,
        "routableModels": (f"{report.profile.routable_model_count} / {report.profile.model_count}"),
        "profileFreshness": report.profile.freshness.value.upper(),
        "freshness": freshness,
        "freshnessAge": age(report.snapshot_age_seconds),
        "stale": report.is_stale,
        "provider": report.provider,
        "source": report.source.value,
        "warnings": list(report.warnings),
    }


def map_provider_status(status: ProviderStatus | None) -> dict[str, Any]:
    """Map typed provider facts without account IDs, plan inference, or raw detail."""
    if status is None:
        return {
            "provider": "OpenAI Codex",
            "status": "Unknown",
            "statusValue": "UNKNOWN",
            "authentication": "Unknown",
            "lastRefresh": "Unknown",
            "data": "Unknown",
            "guidance": "Provider status has not been checked.",
        }
    if status.authentication is ProviderAuthentication.NOT_AUTHENTICATED:
        label = "Not authenticated"
        status_value = "UNKNOWN"
        guidance = "Codex CLI authentication is required. Run `codex login`, then refresh."
    elif status.connection is ProviderConnection.UNAVAILABLE:
        label = "Unavailable"
        status_value = "ERROR"
        guidance = "Run `quotapilot doctor` to inspect Codex CLI availability."
    elif status.connection is ProviderConnection.CONNECTED:
        label = "Connected"
        status_value = "SUCCESS"
        guidance = "Authentication is managed by Codex CLI."
    else:
        label = "Unknown"
        status_value = "UNKNOWN"
        guidance = "Provider status could not be determined."
    if status.using_persisted_data:
        data = "Using persisted data · STALE" if status.stale else "Using persisted data"
    elif status.last_refresh_at is not None:
        data = "Stale" if status.stale else "Fresh"
    else:
        data = "Unknown"
    return {
        "provider": "OpenAI Codex",
        "status": label,
        "statusValue": status_value,
        "authentication": (
            "Codex CLI"
            if status.authentication is ProviderAuthentication.AUTHENTICATED
            else label
            if status.authentication is ProviderAuthentication.NOT_AUTHENTICATED
            else "Unknown"
        ),
        "lastRefresh": timestamp(status.last_refresh_at),
        "data": data,
        "guidance": guidance,
    }


def map_usage_report(report: BudgetReport) -> list[dict[str, Any]]:
    return [map_pool_assessment(pool) for pool in report.pools]


def map_pool_assessment(pool: PoolBudgetAssessment) -> dict[str, Any]:
    return {
        "poolId": pool.pool_id,
        "name": pool.pool_name or pool.pool_id,
        "actual": pool.actual_usage,
        "actualText": fraction(pool.actual_usage),
        "expected": pool.expected_usage,
        "expectedText": fraction(pool.expected_usage),
        "delta": pool.pace_delta,
        "deltaText": ("Unknown" if pool.pace_delta is None else f"{pool.pace_delta:+.1%}"),
        "state": pool.state.value.upper(),
        "reset": timestamp(pool.resets_at),
        "warnings": list(pool.warnings),
    }


def map_daily_forecast(forecast: DailyForecast) -> list[dict[str, Any]]:
    return [
        {
            "date": point.date.isoformat(),
            "weekday": point.date.weekday(),
            "today": point.is_today,
            "projected": point.projected_used_fraction,
            "projectedText": f"{point.projected_used_fraction:.0%}",
            "remainingText": f"{point.projected_remaining_fraction:.0%}",
            "expectedText": f"{point.expected_used_fraction:.0%}",
            "deltaText": f"{point.delta_from_expected:+.0%}",
            "statusValue": point.state.value.upper(),
            "endsAtReset": point.ends_at_reset,
        }
        for point in forecast.points
    ]


def map_usage_point(
    captured_at: datetime,
    pool: PoolBudgetAssessment | None,
) -> dict[str, Any]:
    """Retain the persisted History row mapping; Usage no longer charts it."""
    return {
        "capturedAt": captured_at.isoformat(),
        "capturedText": timestamp(captured_at),
        "actual": pool.actual_usage if pool is not None else None,
        "expected": pool.expected_usage if pool is not None else None,
        "delta": pool.pace_delta if pool is not None else None,
        "statusValue": pool.state.value.upper() if pool is not None else "UNKNOWN",
        "actualText": fraction(pool.actual_usage if pool is not None else None),
        "expectedText": fraction(pool.expected_usage if pool is not None else None),
    }


def map_models(views: Iterable[ModelCapabilityView]) -> list[dict[str, Any]]:
    return [
        {
            "modelId": view.model_id,
            "provider": view.provider,
            "routable": view.routable,
            "routableText": "Yes" if view.routable else "No",
            "power": decimal(view.relative_power),
            "cost": decimal(view.relative_cost),
            "latency": decimal(view.relative_latency),
            "effort": ", ".join(view.effort_order or ()) or "Unknown",
            "profile": view.profile_name or "Unknown",
            "source": view.profile_source.value if view.profile_source else "Unknown",
            "confidence": (view.profile_confidence.value if view.profile_confidence else "Unknown"),
            "verified": view.verified_at.isoformat() if view.verified_at else "Unknown",
            "freshness": view.freshness.value.upper() if view.freshness else "UNKNOWN",
            "stale": bool(view.freshness and view.freshness.value == "stale"),
            "evidence": list(view.profile_evidence),
            "warnings": list(view.warnings),
        }
        for view in views
    ]


def map_route(recommendation: RoutingRecommendation) -> dict[str, Any]:
    profile = recommendation.task_profile
    return {
        "model": recommendation.selected_model_id,
        "effort": recommendation.selected_effort or "Unavailable",
        "confidence": recommendation.confidence.value,
        "difficulty": recommendation.difficulty_score,
        "pressure": recommendation.quota_pressure,
        "pressureText": decimal(recommendation.quota_pressure),
        "taskClass": profile.task_class.value,
        "profileSource": profile.profile_source.value,
        "profile": {
            "complexity": profile.complexity,
            "ambiguity": profile.ambiguity,
            "failureCost": profile.failure_cost,
            "verifiability": profile.verifiability,
            "contextDemand": profile.context_demand,
            "latencySensitivity": profile.latency_sensitivity,
        },
        "explanation": [_map_explanation(item) for item in recommendation.explanation],
        "escalation": [
            {
                "model": step.model_id,
                "effort": step.effort or "default",
                "reason": step.reason,
            }
            for step in recommendation.escalation_path
        ],
        "warnings": list(recommendation.warnings),
    }


def map_execution_plan(plan: ExecutionPlan) -> dict[str, Any]:
    return {
        "executionId": plan.execution_id,
        "model": plan.model_id,
        "effort": plan.effort or "Unavailable",
        "workingDirectory": str(plan.working_directory),
        "quotaState": decimal(plan.budget_pressure),
        "approval": "Required" if plan.requires_confirmation else "Not required",
        "requiresConfirmation": plan.requires_confirmation,
        "timeout": duration(plan.timeout_seconds),
        "timeoutSeconds": plan.timeout_seconds,
        "maxAttempts": plan.max_attempts,
        "dryRun": plan.dry_run,
        "taskClass": plan.task_class.value,
        "escalation": [
            f"{step.model_id} · {step.effort or 'default'}" for step in plan.escalation_path
        ],
        "warnings": list(plan.warnings),
    }


def map_execution_result(result: ExecutionResult) -> dict[str, Any]:
    return {
        "status": result.status.value.upper(),
        "model": result.model_id,
        "effort": result.effort or "Unavailable",
        "attempts": result.attempt_count,
        "retries": result.retry_count,
        "escalations": result.escalation_count,
        "failureClass": result.failure_class.value if result.failure_class else "None",
        "message": result.message or "",
    }
