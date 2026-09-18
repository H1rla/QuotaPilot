"""Phase 8 GUI mappings, commands, settings, privacy, and QML smoke."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Coroutine
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import ValidationError

from quotapilot.budget.models import BudgetState
from quotapilot.capabilities.models import (
    ModelCapabilityView,
    ProfileFreshness,
    ProvenanceConfidence,
    ProvenanceSource,
)
from quotapilot.config import AppConfig, load_effective_config, save_user_config
from quotapilot.execution.models import ExecutionPlan
from quotapilot.gui.commands import filter_commands
from quotapilot.gui.controllers.app_controller import AppController
from quotapilot.gui.dependencies import build_dependencies
from quotapilot.gui.mappers import (
    map_execution_plan,
    map_models,
    map_overview,
    map_route,
)
from quotapilot.gui.viewmodels.overview import OverviewViewModel
from quotapilot.gui.viewmodels.route import RouteViewModel
from quotapilot.gui.viewmodels.settings import validate_settings_update
from quotapilot.observability.models import (
    ProfileStatus,
    SnapshotSource,
    StatusPool,
    StatusReport,
)
from quotapilot.routing.models import (
    CandidateScore,
    ProfileSource,
    QuotaPressureSource,
    RecommendationConfidence,
    RoutingRecommendation,
    RoutingStep,
    TaskClass,
    TaskProfile,
)

NOW = datetime(2026, 9, 18, 12, tzinfo=UTC)


class _ImmediateRunner:
    def start(
        self,
        factory: Any,
        on_success: Any,
        on_error: Any,
    ) -> None:
        import asyncio

        try:
            coroutine = cast(Coroutine[Any, Any, Any], factory())
            on_success(asyncio.run(coroutine))
        except Exception as exc:  # noqa: BLE001 - mirrors GUI boundary
            on_error(exc)


def _status(*, stale: bool = False, unknown: bool = False) -> StatusReport:
    captured = NOW - timedelta(minutes=18) if stale else NOW
    pool = StatusPool(
        pool_id="weekly",
        name="Weekly",
        state=BudgetState.UNKNOWN if unknown else BudgetState.OVER,
        used_fraction=None if unknown else 0.67,
        remaining_fraction=None if unknown else 0.33,
        today_budget_fraction=None if unknown else 0.038,
        resets_at=NOW + timedelta(days=4, hours=18),
    )
    return StatusReport(
        provider="openai-codex",
        source=SnapshotSource.PERSISTED_FALLBACK,
        captured_at=captured,
        evaluated_at=NOW,
        snapshot_age_seconds=1080.0 if stale else 0.0,
        is_stale=stale,
        pools=(pool,),
        effective_pressure=None if unknown else 0.70,
        binding_pool_id="weekly",
        profile=ProfileStatus(
            evaluated_on=date(2026, 9, 18),
            freshness=ProfileFreshness.STALE if stale else ProfileFreshness.FRESH,
            model_count=6,
            routable_model_count=3,
            profiled_model_count=3,
        ),
        warnings=("provider_refresh_failed_using_persisted_snapshot",),
    )


def _profile() -> TaskProfile:
    return TaskProfile(
        summary="private raw task text",
        complexity=0.7,
        ambiguity=0.5,
        failure_cost=0.6,
        verifiability=0.7,
        context_demand=0.8,
        latency_sensitivity=0.3,
        task_class=TaskClass.REPOSITORY_CHANGE,
        tags=("class:repository_change",),
        profile_source=ProfileSource.HEURISTIC,
    )


def _recommendation() -> RoutingRecommendation:
    return RoutingRecommendation(
        task_profile=_profile(),
        difficulty_score=0.68,
        required_power=0.72,
        capability_floor=0.64,
        effort_demand=0.70,
        quota_pressure=0.70,
        quota_pressure_source=QuotaPressureSource.BUDGET_REPORT,
        binding_pool_id="weekly",
        selected_model_id="gpt-5.6-terra",
        selected_effort="high",
        candidate_scores=(
            CandidateScore(
                model_id="gpt-5.6-terra",
                selectable=True,
                eligible=True,
            ),
        ),
        escalation_path=(
            RoutingStep(
                model_id="gpt-5.6-sol",
                effort="medium",
                reason="stronger capability",
            ),
        ),
        alternatives=(),
        explanation=("Sufficient capability with lower quota cost.",),
        warnings=(),
        confidence=RecommendationConfidence.MEDIUM,
    )


def _plan(tmp_path: Path, *, dry_run: bool) -> ExecutionPlan:
    return ExecutionPlan(
        execution_id="execution-1",
        provider="openai-codex",
        model_id="gpt-5.6-terra",
        effort="high",
        initial_model_id="gpt-5.6-terra",
        initial_effort="high",
        task_payload="private raw task text",
        task_hash="sha256:" + "a" * 64,
        task_profile=_profile(),
        task_class=TaskClass.REPOSITORY_CHANGE,
        recommendation_link="sha256:" + "b" * 64,
        attempt_number=1,
        escalation_index=0,
        max_attempts=3,
        dry_run=dry_run,
        requires_confirmation=not dry_run,
        working_directory=tmp_path,
        timeout_seconds=900,
        adapter_name="codex-cli",
        command_preview=("codex", "exec", "-"),
        quota_snapshot_captured_at=NOW,
        budget_pressure=0.70,
        binding_pool_id="weekly",
        planned_at=NOW,
        escalation_path=(
            RoutingStep(
                model_id="gpt-5.6-sol",
                effort="medium",
                reason="stronger capability",
            ),
        ),
    )


def test_overview_mapping_preserves_unknown_stale_and_provider_fallback() -> None:
    missing = map_overview(None)
    unknown = map_overview(_status(unknown=True))
    stale = map_overview(_status(stale=True))

    assert missing["remaining"] == "Unknown"
    assert missing["available"] is False
    assert unknown["remaining"] == "Unknown"
    assert unknown["state"] == "UNKNOWN"
    assert unknown["pressure"] == "Unknown"
    assert unknown["source"] == "persisted_fallback"
    assert stale["stale"] is True
    assert stale["freshness"] == "Snapshot 18m ago · STALE"


def test_models_route_and_execution_mappings_are_ui_ready_and_private(
    tmp_path: Path,
) -> None:
    model_rows = map_models(
        (
            ModelCapabilityView(
                model_id="gpt-5.6-terra",
                provider="openai-codex",
                selectable=True,
                routable=True,
                relative_power=0.75,
                relative_cost=0.55,
                relative_latency=0.34,
                effort_order=("low", "medium", "high"),
                field_sources={"relative_power": "profile/manual"},
                profile_name="codex-v1",
                profile_source=ProvenanceSource.MANUAL,
                profile_confidence=ProvenanceConfidence.PROVISIONAL,
                profile_evidence=("Reviewed local capability profile",),
                verified_at=date(2026, 9, 18),
                freshness=ProfileFreshness.FRESH,
            ),
        )
    )
    route = map_route(_recommendation())
    dry_run = map_execution_plan(_plan(tmp_path, dry_run=True))
    approval = map_execution_plan(_plan(tmp_path, dry_run=False))
    serialized = json.dumps({"models": model_rows, "route": route, "plan": approval})

    assert model_rows[0]["routableText"] == "Yes"
    assert model_rows[0]["evidence"] == ["Reviewed local capability profile"]
    assert route["model"] == "gpt-5.6-terra"
    assert route["escalation"][0]["model"] == "gpt-5.6-sol"
    assert dry_run["dryRun"] is True
    assert dry_run["approval"] == "Not required"
    assert approval["requiresConfirmation"] is True
    assert approval["approval"] == "Required"
    assert "private raw task text" not in serialized
    assert "account_id" not in serialized
    assert "raw_observation" not in serialized


def test_command_palette_filters_and_excludes_real_execution_action() -> None:
    route = filter_commands("rou")
    reserve = filter_commands("reserve")

    assert route[0].id == "route"
    assert reserve[0].id == "settings-budget"
    assert {command.id for command in filter_commands("")} >= {
        "refresh",
        "details",
        "settings",
    }
    assert "approve-execute" not in {command.id for command in filter_commands("")}


def test_command_palette_actions_navigate_and_toggle_details(tmp_path: Path) -> None:
    effective = load_effective_config(
        path=tmp_path / "missing.yaml",
        environ={},
        cli_overrides={"database.path": str(tmp_path / "gui.db")},
    )
    controller = AppController(build_dependencies(effective), smoke_mode=True)

    controller.triggerCommand("settings")
    assert controller.pageName == "Settings"
    assert controller.detailsVisible is False
    controller.triggerCommand("details")
    assert controller.detailsVisible is True


def test_overview_provider_unavailable_and_route_without_snapshot_are_actionable() -> None:
    class FailingStatus:
        async def get_status(self, **_kwargs: Any) -> StatusReport | None:
            raise RuntimeError("raw-provider-secret")

    class EmptyRouting:
        async def recommend_latest(self, *_args: Any, **_kwargs: Any) -> None:
            return None

    effective = SimpleNamespace(
        config=SimpleNamespace(provider=SimpleNamespace(default="openai-codex"))
    )
    overview_dependencies = SimpleNamespace(
        status_service=FailingStatus(),
        effective=effective,
        provider=object(),
    )
    overview = OverviewViewModel(
        cast(Any, overview_dependencies),
        cast(Any, _ImmediateRunner()),
    )
    overview.refresh()

    route_dependencies = SimpleNamespace(
        routing_service=EmptyRouting(),
        effective=effective,
    )
    route = RouteViewModel(cast(Any, route_dependencies), cast(Any, _ImmediateRunner()))
    route.analyze("Implement a bounded local change")

    assert overview.hasError is True
    assert overview.errorAction == "Retry"
    assert "raw-provider-secret" not in str(overview.errorMessage)
    assert route.hasResult is False
    assert route.hasError is True
    assert route.errorAction == "Refresh"


def test_settings_validation_and_atomic_round_trip(tmp_path: Path) -> None:
    updated = validate_settings_update(
        AppConfig(),
        reserve_fraction="0.20",
        timezone="Asia/Tokyo",
        stale_after_seconds="1200",
        unknown_quota_pressure="0.45",
        execution_mode="always_confirm",
        timeout_seconds="600",
        max_attempts="4",
        max_same_step_retries="1",
    )
    path = save_user_config(updated, path=tmp_path / "config.yaml")
    loaded = load_effective_config(path=path, environ={})

    assert loaded.config == updated
    assert loaded.config.budget.timezone == "Asia/Tokyo"
    assert not list(tmp_path.glob("*.tmp"))

    with pytest.raises((ValueError, ValidationError)):
        validate_settings_update(
            AppConfig(),
            reserve_fraction="unlimited",
            timezone="UTC",
            stale_after_seconds="1200",
            unknown_quota_pressure="0.5",
            execution_mode="always_confirm",
            timeout_seconds="600",
            max_attempts="3",
            max_same_step_retries="1",
        )


def test_qml_offscreen_smoke_uses_no_provider_credentials(tmp_path: Path) -> None:
    environment = dict(os.environ)
    environment.update(
        {
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "OPENAI_API_KEY": "must-not-be-used-by-smoke",
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from quotapilot.gui.app import run_gui; raise SystemExit(run_gui(smoke_test=True))",
        ],
        cwd=Path(__file__).parents[2],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "must-not-be-used-by-smoke" not in result.stdout + result.stderr
