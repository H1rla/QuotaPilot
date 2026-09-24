"""Phase 9.2A interaction tests; fake services never launch an execution adapter."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from rich.text import Text
from textual.widgets import Button, Input, OptionList, Static, TextArea

from quotapilot.budget.models import BudgetReport
from quotapilot.capabilities.models import ModelCapabilityView, ProfileFreshness
from quotapilot.config import load_effective_config
from quotapilot.domain.capability import CapabilitySet
from quotapilot.execution.models import (
    ExecutionPlan,
    ExecutionPolicy,
    ExecutionResult,
    ExecutionStatus,
    FailureClass,
)
from quotapilot.execution.planner import ExecutionPlanner
from quotapilot.providers.base import ProviderConnection
from quotapilot.routing.errors import NoRoutableModelError
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
from quotapilot.services.execution import ExecutionService
from quotapilot.services.routing import RoutingContext, RoutingService
from quotapilot.tui.app import QuotaPilotApp
from quotapilot.tui.dependencies import build_dependencies
from quotapilot.tui.localization import Localizer
from quotapilot.tui.screens.execute import ExecuteView
from quotapilot.tui.screens.models import ModelsView
from quotapilot.tui.screens.quit_execution import QuitExecutionOverlay
from quotapilot.tui.screens.route import RouteView
from quotapilot.tui.state import Destination, OverviewState
from quotapilot.tui.viewmodels.execute import ExecuteState
from quotapilot.tui.viewmodels.models import ModelRow, ModelsState

NOW = datetime(2026, 9, 24, 12, tzinfo=UTC)
TASK = "Inspect a bounded synthetic task"


def _context(*, unknown: bool = False, stale: bool = False, summary: str = TASK) -> RoutingContext:
    profile = TaskProfile(
        summary=summary,
        complexity=0.4,
        ambiguity=0.3,
        failure_cost=0.3,
        verifiability=0.8,
        context_demand=0.4,
        latency_sensitivity=0.5,
        task_class=TaskClass.LOCAL_IMPLEMENTATION,
        profile_source=ProfileSource.HEURISTIC,
    )
    recommendation = RoutingRecommendation(
        task_profile=profile,
        difficulty_score=0.4,
        required_power=0.5,
        capability_floor=0.4,
        effort_demand=0.5,
        quota_pressure=0.5 if unknown else 0.3,
        quota_pressure_source=(
            QuotaPressureSource.FALLBACK_UNKNOWN if unknown else QuotaPressureSource.BUDGET_REPORT
        ),
        binding_pool_id=None if unknown else "weekly",
        selected_model_id="synthetic-model",
        selected_effort="medium",
        candidate_scores=(
            CandidateScore(model_id="synthetic-model", selectable=True, eligible=True),
        ),
        escalation_path=(RoutingStep(model_id="strong-model", effort="high", reason="risk"),),
        alternatives=(),
        explanation=("synthetic reason",),
        warnings=(),
        confidence=RecommendationConfidence.HIGH,
    )
    budget = BudgetReport(
        captured_at=NOW,
        evaluated_at=NOW,
        snapshot_age_seconds=1200 if stale else 0,
        is_stale=stale,
        reserve_fraction=0.1,
        timezone="UTC",
        pools=(),
        effective_pressure=None if unknown else 0.3,
        binding_pool_id=None if unknown else "weekly",
    )
    return RoutingContext(
        provider="openai-codex",
        recommendation=recommendation,
        budget_report=budget,
        capabilities=CapabilitySet(models=()),
        snapshot_captured_at=NOW,
    )


def _plan(directory: Path, *, dry_run: bool, summary: str = TASK) -> ExecutionPlan:
    context = _context(summary=summary)
    return ExecutionPlanner(ExecutionPolicy(), id_factory=lambda: "synthetic-execution").build(
        context.recommendation,
        context.budget_report,
        provider="openai-codex",
        task_payload=summary,
        working_directory=directory,
        dry_run=dry_run,
        adapter_name="fake-adapter",
        command_preview=("fake-adapter", "--no-shell"),
        planned_at=NOW,
    )


def _result(plan: ExecutionPlan, status: ExecutionStatus) -> ExecutionResult:
    return ExecutionResult(
        execution_id=plan.execution_id,
        task_hash=plan.task_hash,
        started_at=NOW,
        finished_at=NOW,
        model_id=plan.model_id,
        effort=plan.effort,
        status=status,
        failure_class=(
            FailureClass.TIMEOUT
            if status is ExecutionStatus.FAILED
            else FailureClass.USER_CANCELLED
            if status is ExecutionStatus.CANCELLED
            else None
        ),
        attempt_count=1,
        stdout_summary="bounded output",
    )


class _Routing:
    def __init__(self, context: RoutingContext | None = None, *, error: bool = False) -> None:
        self.context = context
        self.error = error
        self.calls = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.delay = False

    async def recommend_latest_context(self, summary: str, **_kwargs: Any) -> RoutingContext | None:
        self.calls += 1
        self.started.set()
        if self.delay:
            await self.release.wait()
        if self.error:
            raise NoRoutableModelError("synthetic no route")
        if self.context is None:
            return None
        return _context(
            unknown=self.context.recommendation.quota_pressure_source
            is QuotaPressureSource.FALLBACK_UNKNOWN,
            stale=self.context.budget_report.is_stale,
            summary=summary.strip(),
        )


class _Execution:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.create_calls: list[bool] = []
        self.run_calls = 0
        self.status = ExecutionStatus.SUCCEEDED
        self.change_plan = False
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.delay = False
        self.approval_calls: list[ExecutionPlan] = []

    async def create_plan(
        self, task: str, *, working_directory: Path, dry_run: bool
    ) -> ExecutionPlan:
        self.create_calls.append(dry_run)
        assert working_directory == Path.cwd()
        return _plan(self.directory, dry_run=dry_run, summary=task)

    async def run_plan(
        self,
        plan: ExecutionPlan,
        *,
        approval_handler: Any,
        plan_change_handler: Any,
    ) -> ExecutionResult:
        self.run_calls += 1
        self.started.set()
        self.approval_calls.append(plan)
        if not await approval_handler(plan):
            return _result(plan, ExecutionStatus.DENIED)
        if self.change_plan:
            candidate = plan.model_copy(
                update={"model_id": "strong-model", "effort": "high", "escalation_index": 1}
            )
            self.approval_calls.append(candidate)
            if not await plan_change_handler(candidate):
                return _result(plan, ExecutionStatus.DENIED)
        if self.delay:
            await self.release.wait()
        return _result(plan, self.status)


def _app(
    tmp_path: Path,
    *,
    language: str = "en",
    routing: _Routing | None = None,
    execution: _Execution | None = None,
) -> tuple[QuotaPilotApp, _Routing, _Execution]:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(f"appearance:\n  language: {language}\n", encoding="utf-8")
    dependencies = build_dependencies(load_effective_config(path=config_file, environ={}))
    route = routing or _Routing(_context())
    execute = execution or _Execution(tmp_path)
    dependencies = replace(
        dependencies,
        routing_service=cast(RoutingService, route),
        execution_service=cast(ExecutionService, execute),
    )
    return (
        QuotaPilotApp(dependencies, localizer=Localizer(language), enable_startup=False),
        route,
        execute,
    )


async def _analyze(app: QuotaPilotApp, pilot: Any) -> None:
    app.navigate(Destination.ROUTE)
    editor = app.query_one("#route-task", TextArea)
    editor.load_text(TASK)
    await pilot.pause()
    app.action_analyze_task()
    await pilot.pause()
    assert app.route_view_model.state.status == "ready"


@pytest.mark.asyncio
async def test_route_entry_and_analysis_are_async_and_focus_aware(tmp_path: Path) -> None:
    route = _Routing(_context())
    route.delay = True
    app, _, _ = _app(tmp_path, routing=route)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.navigate(Destination.ROUTE)
        await pilot.pause()
        assert app.focused is app.query_one("#route-task", TextArea)
        await pilot.press("h", "j", "k", "l", "q", "enter")
        assert app.query_one("#route-task", TextArea).text.startswith("hjklq")
        assert route.calls == 0
        app.query_one("#route-task", TextArea).load_text(TASK)
        app.action_analyze_task()
        app.action_analyze_task()
        await route.started.wait()
        assert app.route_view_model.state.status == "analyzing"
        assert route.calls == 1
        route.release.set()
        await pilot.pause()
        assert app.route_view_model.state.status == "ready"
        assert app.query_one("#route-result").display


@pytest.mark.asyncio
async def test_route_ctrl_enter_analyzes_without_plain_enter_side_effect(tmp_path: Path) -> None:
    app, route, _ = _app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.navigate(Destination.ROUTE)
        editor = app.query_one("#route-task", TextArea)
        editor.load_text(TASK)
        editor.focus()
        await pilot.press("enter")
        assert route.calls == 0
        await pilot.press("ctrl+enter")
        await pilot.pause()
        assert route.calls == 1
        assert app.route_view_model.state.status == "ready"
        await pilot.press("escape")
        assert app.current_destination is Destination.ROUTE
        assert app.focused is app.query_one(RouteView)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("context", "error", "expected"),
    [
        (None, False, "route.no_snapshot"),
        (_context(), True, "route.no_model"),
    ],
)
async def test_route_unavailable_states(
    tmp_path: Path, context: RoutingContext | None, error: bool, expected: str
) -> None:
    app, _, _ = _app(tmp_path, routing=_Routing(context, error=error))
    async with app.run_test() as pilot:
        app.navigate(Destination.ROUTE)
        app.query_one("#route-task", TextArea).load_text(TASK)
        app.action_analyze_task()
        await pilot.pause()
        assert app.route_view_model.state.message_id == expected
        assert app.query_one("#route-result").display is False


@pytest.mark.asyncio
async def test_route_empty_unknown_stale_details_and_japanese(tmp_path: Path) -> None:
    app, route, _ = _app(
        tmp_path, language="ja", routing=_Routing(_context(unknown=True, stale=True))
    )
    async with app.run_test(size=(80, 24)) as pilot:
        app.navigate(Destination.ROUTE)
        app.action_analyze_task()
        await pilot.pause()
        assert route.calls == 0
        assert app.route_view_model.state.message_id == "route.empty"
        app.query_one("#route-task", TextArea).load_text(TASK)
        app.action_analyze_task()
        await pilot.pause()
        assert app.route_view_model.state.status == "ready"
        assert "古い" in str(app.query_one("#route-context", Static).content)
        assert "不明" in str(app.query_one("#route-context", Static).content)
        context_text = app.query_one("#route-context", Static).content
        assert isinstance(context_text, Text)
        assert any(
            span.style == app.current_theme.variables["stale"] for span in context_text.spans
        )
        app.query_one(RouteView).focus()
        await pilot.press("ctrl+d")
        assert app.query_one("#route-details", Static).display is True


@pytest.mark.asyncio
async def test_route_provider_unavailable_and_generic_error_are_actionable(tmp_path: Path) -> None:
    class FailingRouting(_Routing):
        async def recommend_latest_context(
            self, summary: str, **_kwargs: Any
        ) -> RoutingContext | None:
            del summary
            raise RuntimeError("secret provider detail")

    app, _, _ = _app(tmp_path, routing=FailingRouting(_context()))
    async with app.run_test() as pilot:
        await pilot.pause()
        app._publish_overview(OverviewState(connection=ProviderConnection.UNAVAILABLE))
        app.navigate(Destination.ROUTE)
        assert "Provider unavailable" in str(app.query_one("#route-message", Static).content)
        app.query_one("#route-task", TextArea).load_text(TASK)
        app.action_analyze_task()
        await pilot.pause()
        assert app.route_view_model.state.status == "error"
        assert "secret provider detail" not in str(app.query_one("#route-message", Static).content)


@pytest.mark.asyncio
async def test_dry_run_uses_actual_planner_boundary_and_never_runs(tmp_path: Path) -> None:
    app, _, execute = _app(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        await _analyze(app, pilot)
        app.query_one("#route-dry-run", Button).press()
        await pilot.pause()
        assert app.current_destination is Destination.EXECUTE
        assert execute.create_calls == [True]
        assert execute.run_calls == 0
        assert app.execute_view_model.state.plan is not None
        assert app.execute_view_model.state.plan.dry_run
        assert app.query_one("#execute-approve", Button).display is False
        assert "DRY RUN" in str(app.query_one("#execute-fields", Static).content)


@pytest.mark.asyncio
async def test_execute_requires_focused_explicit_approval_and_shows_result(tmp_path: Path) -> None:
    app, _, execute = _app(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await _analyze(app, pilot)
        app.query_one("#route-execute", Button).press()
        await pilot.pause()
        assert execute.create_calls == [False]
        assert execute.run_calls == 0
        assert app.focused is app.query_one("#execute-cancel", Button)
        assert str(tmp_path) in str(app.query_one("#execute-fields", Static).content)
        app.query_one(ExecuteView).focus()
        await pilot.press("enter")
        assert execute.run_calls == 0
        app.query_one("#execute-approve", Button).focus()
        await pilot.press("enter")
        await pilot.pause()
        assert execute.run_calls == 1
        assert app.execute_view_model.state.result is not None
        assert app.execute_view_model.state.result.status is ExecutionStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_execute_escape_cancels_before_adapter(tmp_path: Path) -> None:
    app, _, execute = _app(tmp_path)
    async with app.run_test() as pilot:
        await _analyze(app, pilot)
        app.query_one("#route-execute", Button).press()
        await pilot.pause()
        await pilot.press("escape")
        assert app.current_destination is Destination.ROUTE
        assert execute.run_calls == 0


@pytest.mark.asyncio
async def test_changed_plan_requires_second_approval(tmp_path: Path) -> None:
    execute = _Execution(tmp_path)
    execute.change_plan = True
    app, _, _ = _app(tmp_path, execution=execute)
    async with app.run_test() as pilot:
        await _analyze(app, pilot)
        app.query_one("#route-execute", Button).press()
        await pilot.pause()
        app.query_one("#execute-approve", Button).press()
        await pilot.pause()
        assert len(execute.approval_calls) == 2
        assert app.execute_view_model.state.status == "awaiting_approval"
        assert "strong-model" in str(app.query_one("#execute-fields", Static).content)
        assert app.focused is app.query_one("#execute-cancel", Button)
        app.query_one("#execute-approve", Button).press()
        await pilot.pause()
        assert app.execute_view_model.state.result is not None
        assert app.execute_view_model.state.result.status is ExecutionStatus.SUCCEEDED


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [ExecutionStatus.FAILED, ExecutionStatus.CANCELLED])
async def test_execute_failed_and_cancelled_results(
    tmp_path: Path, status: ExecutionStatus
) -> None:
    execute = _Execution(tmp_path)
    execute.status = status
    app, _, _ = _app(tmp_path, execution=execute)
    async with app.run_test() as pilot:
        await _analyze(app, pilot)
        app.query_one("#route-execute", Button).press()
        await pilot.pause()
        app.query_one("#execute-approve", Button).press()
        await pilot.pause()
        assert app.execute_view_model.state.result is not None
        assert app.execute_view_model.state.result.status is status


@pytest.mark.asyncio
async def test_running_execution_blocks_palette_navigation_and_cancels(tmp_path: Path) -> None:
    execute = _Execution(tmp_path)
    execute.delay = True
    app, _, _ = _app(tmp_path, execution=execute)
    async with app.run_test() as pilot:
        await _analyze(app, pilot)
        app.query_one("#route-execute", Button).press()
        await pilot.pause()
        app.query_one("#execute-approve", Button).press()
        await execute.started.wait()
        app.run_command("navigate:models")
        assert app.current_destination is Destination.EXECUTE
        app.run_command("quit")
        await pilot.pause()
        assert isinstance(app.screen, QuitExecutionOverlay)
        assert app.is_running
        app.screen.query_one("#quit-cancel", Button).press()
        await pilot.pause()
        assert not app.is_running or app.execute_view_model.state.status == "cancelled"


@pytest.mark.asyncio
async def test_escape_during_execution_uses_cancellation_path(tmp_path: Path) -> None:
    execute = _Execution(tmp_path)
    execute.delay = True
    app, _, _ = _app(tmp_path, execution=execute)
    async with app.run_test() as pilot:
        await _analyze(app, pilot)
        app.query_one("#route-execute", Button).press()
        await pilot.pause()
        app.query_one("#execute-approve", Button).press()
        await execute.started.wait()
        await pilot.press("escape")
        await pilot.pause()
        assert app.execute_view_model.state.status == "cancelled"
        assert app.current_destination is Destination.ROUTE


@pytest.mark.asyncio
async def test_models_filter_detail_and_compact_reflow(tmp_path: Path) -> None:
    app, _, _ = _app(tmp_path, language="ja")
    rows = (
        ModelRow(
            ModelCapabilityView(
                model_id="exact-model-a",
                provider="openai-codex",
                selectable=True,
                routable=True,
                relative_power=0.8,
                relative_cost=None,
                relative_latency=None,
                effort_order=("medium",),
                freshness=ProfileFreshness.FRESH,
            ),
            ("medium",),
        ),
        ModelRow(
            ModelCapabilityView(
                model_id="別モデル-b",
                provider="openai-codex",
                selectable=False,
                routable=False,
                relative_power=None,
                relative_cost=None,
                relative_latency=None,
                effort_order=None,
                freshness=ProfileFreshness.STALE,
            ),
            (),
        ),
    )
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        app.models_view_model.state = ModelsState(status="ready", models=rows)
        app.navigate(Destination.MODELS)
        await pilot.pause()
        view = app.query_one(ModelsView)
        view.update_state(app.models_view_model.state)
        assert view.compact
        stale_prompt = app.query_one("#models-list", OptionList).get_option_at_index(1).prompt
        assert isinstance(stale_prompt, Text)
        assert stale_prompt.spans[0].style == app.current_theme.variables["stale"]
        await pilot.press("slash")
        assert app.focused is app.query_one("#models-filter", Input)
        await pilot.press("別", "モ", "デ", "ル")
        assert len(view._visible) == 1
        await pilot.press("escape")
        assert app.query_one("#models-filter", Input).value == ""
        view.focus_list()
        await pilot.press("enter")
        assert view.detail_open
        assert app.query_one("#models-list-region").display is False
        await pilot.resize_terminal(120, 30)
        assert app.query_one("#models-list-region").display is True
        assert "不明" in str(app.query_one("#models-detail", Static).content)


def test_no_raw_account_or_credentials_in_viewmodel_state(tmp_path: Path) -> None:
    app, _, _ = _app(tmp_path)
    assert not hasattr(app.route_view_model.state, "account_id")
    assert not hasattr(app.execute_view_model.state, "credentials")


@pytest.mark.asyncio
async def test_context_commands_and_help_preserve_approval_gate(tmp_path: Path) -> None:
    app, _, execute = _app(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await _analyze(app, pilot)
        assert app.command_available("analyze")
        assert app.command_available("recommended_model")
        assert app.command_available("dry_run")
        assert app.command_available("open_plan")
        app.query_one(RouteView).focus()
        await pilot.press("question_mark")
        assert app.screen.id == "help-overlay"
        await pilot.press("escape")
        app.run_command("open_plan")
        await pilot.pause()
        assert app.current_destination is Destination.EXECUTE
        assert execute.run_calls == 0
        assert app.focused is app.query_one("#execute-cancel", Button)


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(80, 24), (100, 30), (140, 40)])
@pytest.mark.parametrize("language", ["en", "ja"])
@pytest.mark.parametrize("theme", ["quotapilot-dark", "quotapilot-light"])
async def test_route_execute_layout_smoke_matrix(
    tmp_path: Path,
    size: tuple[int, int],
    language: str,
    theme: str,
) -> None:
    app, _, execute = _app(tmp_path, language=language)
    app.theme = theme
    async with app.run_test(size=size) as pilot:
        await _analyze(app, pilot)
        app.query_one("#route-execute", Button).press()
        await pilot.pause()
        assert app.current_destination is Destination.EXECUTE
        assert str(tmp_path) in str(app.query_one("#execute-fields", Static).content)
        assert app.query_one("#execute-warning", Static).display
        assert app.query_one("#execute-cancel", Button).display
        assert app.theme == theme
        app.query_one(ModelsView)
        assert execute.run_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", ["quotapilot-dark", "quotapilot-light"])
@pytest.mark.parametrize(
    ("status", "color_name"),
    [(ExecutionStatus.SUCCEEDED, "success"), (ExecutionStatus.FAILED, "error")],
)
async def test_execute_colors_only_semantic_result_label(
    tmp_path: Path,
    theme: str,
    status: ExecutionStatus,
    color_name: str,
) -> None:
    app, _, _ = _app(tmp_path)
    app.theme = theme
    async with app.run_test(size=(100, 30)) as pilot:
        plan = _plan(tmp_path, dry_run=False)
        app.navigate(Destination.EXECUTE)
        await pilot.pause()
        app.query_one(ExecuteView).update_state(
            ExecuteState(status="result", plan=plan, result=_result(plan, status))
        )
        content = app.query_one("#execute-result", Static).content
        assert isinstance(content, Text)
        assert len(content.spans) == 1
        assert content.spans[0].style == getattr(app.current_theme, color_name)
        assert content.spans[0].end < len(content.plain)


@pytest.mark.asyncio
async def test_very_short_execution_uses_resize_guard(tmp_path: Path) -> None:
    app, _, execute = _app(tmp_path)
    async with app.run_test(size=(60, 18)) as pilot:
        await _analyze(app, pilot)
        app.query_one("#route-execute", Button).press()
        await pilot.pause()
        assert app.query_one("#resize-guard", Static).display
        assert not app.query_one("#body").display
        assert execute.run_calls == 0
        await pilot.press("escape")
        assert app.current_destination is Destination.ROUTE
        assert app.query_one("#body").display
