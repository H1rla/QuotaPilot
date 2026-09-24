"""Persistent Textual application and installed-wheel smoke entry."""

from __future__ import annotations

import asyncio
from asyncio import Future
from pathlib import Path
from typing import cast

from textual import events
from textual.app import App, ComposeResult
from textual.command import CommandPalette
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, ContentSwitcher, Input, OptionList, Static, TextArea

from quotapilot.budget.engine import BudgetEngine
from quotapilot.config import load_effective_config
from quotapilot.execution.models import ExecutionPlan
from quotapilot.observability.doctor import DoctorService
from quotapilot.tui.commands import QuotaPilotCommandProvider
from quotapilot.tui.dependencies import TuiDependencies, build_dependencies
from quotapilot.tui.keymap import app_bindings
from quotapilot.tui.localization import Localizer
from quotapilot.tui.screens.doctor import DoctorView
from quotapilot.tui.screens.execute import ExecuteView
from quotapilot.tui.screens.help import HelpOverlay
from quotapilot.tui.screens.history import HistoryView
from quotapilot.tui.screens.models import ModelsView
from quotapilot.tui.screens.overview import OverviewView
from quotapilot.tui.screens.quit_execution import QuitExecutionOverlay
from quotapilot.tui.screens.route import RouteView
from quotapilot.tui.screens.settings import SettingsView
from quotapilot.tui.screens.usage import UsageView
from quotapilot.tui.state import (
    Destination,
    LayoutMode,
    OverviewState,
    VerticalMode,
    horizontal_mode,
    vertical_mode,
)
from quotapilot.tui.theme import ThemeResolution, register_themes, resolve_theme
from quotapilot.tui.viewmodels.doctor import DoctorViewModel
from quotapilot.tui.viewmodels.execute import ExecuteState, ExecuteViewModel
from quotapilot.tui.viewmodels.models import ModelsViewModel
from quotapilot.tui.viewmodels.overview import OverviewViewModel
from quotapilot.tui.viewmodels.route import RouteViewModel
from quotapilot.tui.viewmodels.settings import SettingsViewModel
from quotapilot.tui.viewmodels.usage import UsageViewModel
from quotapilot.tui.widgets.chrome import HeaderBar
from quotapilot.tui.widgets.contextual_footer import ContextualFooter
from quotapilot.tui.widgets.navigation import DestinationOverlay, NavigationRail


class QuotaPilotApp(App[None]):
    """Keyboard-first shell over existing QuotaPilot service contracts."""

    CSS_PATH = "styles/quotapilot.tcss"
    COMMANDS = {QuotaPilotCommandProvider}
    BINDINGS = app_bindings()
    ENABLE_COMMAND_PALETTE = True

    def __init__(
        self,
        dependencies: TuiDependencies,
        *,
        localizer: Localizer | None = None,
        enable_startup: bool = True,
    ) -> None:
        super().__init__()
        self.dependencies = dependencies
        config = dependencies.effective.config
        self.localizer = localizer or Localizer.from_preference(config.appearance.language)
        self.theme_resolution: ThemeResolution = resolve_theme(config.appearance.tui_theme)
        self.current_destination = Destination.OVERVIEW
        self.layout_mode = LayoutMode.COMPACT
        self.vertical_mode = VerticalMode.SHORT
        self._back_stack: list[Destination] = []
        self._enable_startup = enable_startup
        self._overlay_focus: Widget | None = None
        self._overview_state = OverviewState()
        self.overview_view_model = OverviewViewModel(
            dependencies.status_service,
            dependencies.provider_status_service,
            dependencies.provider,
            selected_provider=config.provider.default,
        )
        self.route_view_model = RouteViewModel(
            dependencies.routing_service, config.provider.default
        )
        self.execute_view_model = ExecuteViewModel(dependencies.execution_service)
        self.models_view_model = ModelsViewModel(
            dependencies.repository,
            dependencies.enricher,
            dependencies.registry,
            config.provider.default,
        )
        self.usage_view_model = (
            UsageViewModel(
                dependencies.repository,
                dependencies.budget_engine or BudgetEngine(config.budget),
                config.provider.default,
            )
            if dependencies.repository is not None
            else None
        )
        self.history_view_model = (
            UsageViewModel(
                dependencies.repository,
                dependencies.budget_engine or BudgetEngine(config.budget),
                config.provider.default,
            )
            if dependencies.repository is not None
            else None
        )
        self.settings_view_model = SettingsViewModel(dependencies.effective)
        self.doctor_view_model = DoctorViewModel(
            dependencies.doctor_service or DoctorService(dependencies.effective)
        )
        self._approved_plan: ExecutionPlan | None = None
        self._pending_plan: ExecutionPlan | None = None
        self._approval_future: Future[bool] | None = None
        self._analysis_pending = False
        self._planning_pending = False
        self._models_pending = False
        self._execution_pending = False
        self._usage_pending = False
        self._usage_refresh_pending = False
        self._history_pending = False
        self._doctor_pending = False
        self._settings_pending = False
        register_themes(cast(App[object], self))
        self.theme = self.theme_resolution.textual_name

    def compose(self) -> ComposeResult:
        with Vertical(id="shell"):
            yield HeaderBar(self.localizer)
            with Horizontal(id="body"):
                yield NavigationRail(self.localizer)
                with ContentSwitcher(initial="overview-view", id="content"):
                    yield OverviewView(self.localizer)
                    yield RouteView(self.localizer)
                    yield ExecuteView(self.localizer)
                    yield ModelsView(self.localizer)
                    yield UsageView(self.localizer)
                    yield HistoryView(self.localizer)
                    yield SettingsView(self.localizer, self.settings_view_model)
                    yield DoctorView(self.localizer)
            yield Static("", id="resize-guard")
            yield ContextualFooter(self.localizer)

    def on_mount(self) -> None:
        self._update_chrome()
        self._apply_size(self.size.width, self.size.height)
        self.call_after_refresh(self._focus_initial)
        if self._enable_startup:
            # The first frame is mounted before even local database work begins.
            self.call_after_refresh(self._start_overview)

    def on_resize(self, event: events.Resize) -> None:
        self._apply_size(event.size.width, event.size.height)

    def on_descendant_focus(self, _event: events.DescendantFocus) -> None:
        self._update_footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "navigation" and event.option.id is not None:
            self.navigate(Destination(event.option.id), focus_content=False)
        elif event.option_list.id == "models-list":
            self.query_one(ModelsView).select(event.option.id)
        elif event.option_list.id == "history-list" and event.option.id is not None:
            self.query_one(HistoryView).select(int(event.option.id))
        elif event.option_list.id == "doctor-list" and event.option.id is not None:
            self.query_one(DoctorView).select(int(event.option.id))
        elif event.option_list.id == "settings-categories" and event.option.id is not None:
            self.query_one(SettingsView).select_category(event.option.id)
        elif event.option_list.id == "settings-fields" and event.option.id is not None:
            self.query_one(SettingsView).select_field(event.option.id)

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "route-task":
            self.route_view_model.set_task(event.text_area.text)
            self.query_one(RouteView).update_state(self.route_view_model.state)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "models-filter":
            self.query_one(ModelsView).update_state(self.models_view_model.state)
        elif event.input.id == "history-filter":
            self.query_one(HistoryView).update_state(
                self.history_view_model.state
            ) if self.history_view_model else None
        elif event.input.id == "settings-filter":
            self.query_one(SettingsView).update_editor_state()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "route-analyze":
                self.action_analyze_task()
            case "route-dry-run":
                self._prepare_execution(dry_run=True)
            case "route-execute":
                self._prepare_execution(dry_run=False)
            case "route-toggle-details":
                self.action_toggle_details()
            case "execute-cancel":
                if self.execute_view_model.active:
                    self.run_worker(self._cancel_execution(), exit_on_error=False)
                else:
                    self.execute_view_model.clear()
                    self._navigate_back()
            case "execute-approve":
                self._approve_execution()
            case "execute-back-route":
                self.navigate(Destination.ROUTE)
            case "history-usage-tab":
                self.query_one(HistoryView).set_section("usage")
            case "history-execution-tab":
                self.query_one(HistoryView).set_section("execution")
            case "settings-stage":
                self.query_one(SettingsView).stage()
            case "settings-cancel-edit":
                self.query_one(SettingsView).close_editor()
            case "settings-save":
                self._save_settings()
            case "settings-discard":
                self.query_one(SettingsView).discard()
            case "doctor-open-settings":
                self.navigate(Destination.SETTINGS)
            case "doctor-open-models":
                self.navigate(Destination.MODELS)

    def _start_overview(self) -> None:
        self.run_worker(
            self.overview_view_model.startup(self._publish_overview),
            name="Overview startup",
            group="overview-refresh",
            exit_on_error=False,
        )

    def _publish_overview(self, state: OverviewState) -> None:
        self._overview_state = state
        view = self.query_one(OverviewView)
        view.update_state(state)
        route = self.query_one(RouteView)
        route.provider_connection = state.connection
        route.update_state(self.route_view_model.state)
        usage = self.query_one(UsageView)
        usage.provider_message_id = state.message_id
        if self.usage_view_model is not None:
            usage.update_state(self.usage_view_model.state)
        self._update_chrome()

    def _focus_initial(self) -> None:
        if self.current_destination is not Destination.OVERVIEW:
            return
        if self.layout_mode in {LayoutMode.WIDE, LayoutMode.STANDARD}:
            self.query_one(NavigationRail).focus()
        else:
            self._current_view().focus()

    def _apply_size(self, columns: int, rows: int) -> None:
        previous = self.layout_mode
        self.layout_mode = horizontal_mode(columns)
        self.vertical_mode = vertical_mode(rows)
        shell = self.query_one("#shell", Vertical)
        shell.set_classes(
            f"layout-{self.layout_mode.value} vertical-{self.vertical_mode.value.replace('_', '-')}"
        )
        self.query_one(ModelsView).set_compact(
            self.layout_mode in {LayoutMode.COMPACT, LayoutMode.CONSTRAINED}
        )
        for view_type in (UsageView, HistoryView, SettingsView, DoctorView):
            self.query_one(view_type).set_compact(
                self.layout_mode in {LayoutMode.COMPACT, LayoutMode.CONSTRAINED}
            )
        unsafe = (
            self.layout_mode is LayoutMode.CONSTRAINED
            or self.vertical_mode is VerticalMode.UNSAFE
            or (
                self.current_destination is Destination.EXECUTE
                and self.execute_view_model.state.plan is not None
                and self.vertical_mode is VerticalMode.VERY_SHORT
            )
        )
        self.query_one("#body", Horizontal).display = not unsafe
        guard = self.query_one("#resize-guard", Static)
        guard.display = unsafe
        guard_message = (
            "resize.execute_body"
            if self.current_destination is Destination.EXECUTE
            and self.vertical_mode is VerticalMode.VERY_SHORT
            else "resize.body"
        )
        guard.update(
            f"{self.localizer.text('resize.title')}\n\n{self.localizer.text(guard_message)}"
        )
        if previous is not self.layout_mode and self.is_mounted:
            focused = self.focused
            if self.layout_mode in {LayoutMode.COMPACT, LayoutMode.CONSTRAINED} and isinstance(
                focused, NavigationRail
            ):
                self._current_view().focus()
        self._update_footer()

    def _update_chrome(self) -> None:
        if not self.is_mounted:
            return
        self.query_one(HeaderBar).update_header(
            self.current_destination,
            self._overview_state.connection,
            self._overview_state.authentication,
            executing=self.execute_view_model.active,
        )
        self.query_one(NavigationRail).set_destination(self.current_destination)
        self._update_footer()

    def _update_footer(self) -> None:
        if not self.is_mounted:
            return
        self.query_one(ContextualFooter).update_context(
            self.current_destination,
            navigation_focused=isinstance(self.focused, NavigationRail),
            compact=self.layout_mode in {LayoutMode.COMPACT, LayoutMode.CONSTRAINED},
        )

    def _current_view(self) -> Widget:
        return cast(
            Widget,
            self.query_one(f"#{self.current_destination.value}-view"),
        )

    def navigate(self, destination: Destination, *, focus_content: bool = True) -> None:
        # Keep active execution visible until it finishes or cancellation completes.
        if self.execute_view_model.active and destination is not Destination.EXECUTE:
            return
        if (
            self.current_destination is Destination.SETTINGS
            and destination is not Destination.SETTINGS
            and self.query_one(SettingsView).arm_discard()
        ):
            return
        if destination is self.current_destination:
            if focus_content:
                self._current_view().focus()
            return
        self._back_stack.append(self.current_destination)
        self.current_destination = destination
        self.query_one(ContentSwitcher).current = f"{destination.value}-view"
        self._update_chrome()
        self._apply_size(self.size.width, self.size.height)
        if destination is Destination.MODELS and self.models_view_model.state.status == "empty":
            self._load_models()
        if destination is Destination.USAGE:
            self._load_usage()
        elif destination is Destination.HISTORY:
            self._load_history()
        elif destination is Destination.DOCTOR:
            self._load_doctor()
        if focus_content:
            if destination is Destination.ROUTE:
                self.query_one(RouteView).focus_editor()
            elif destination is Destination.EXECUTE and self.execute_view_model.state.plan:
                self.query_one(ExecuteView).focus_cancel()
            elif destination is Destination.MODELS:
                self.query_one(ModelsView).focus_list()
            elif destination is Destination.HISTORY:
                self.query_one(HistoryView).focus_list()
            elif destination is Destination.SETTINGS:
                self.query_one(SettingsView).focus_categories()
            elif destination is Destination.DOCTOR:
                self.query_one(DoctorView).focus_list()
            else:
                self._current_view().focus()

    def _navigate_back(self) -> None:
        if (
            self.current_destination is Destination.SETTINGS
            and self.query_one(SettingsView).arm_discard()
        ):
            return
        if self.current_destination is Destination.OVERVIEW and not self._back_stack:
            return
        destination = self._back_stack.pop() if self._back_stack else Destination.OVERVIEW
        self.current_destination = destination
        self.query_one(ContentSwitcher).current = f"{destination.value}-view"
        self._update_chrome()
        self._apply_size(self.size.width, self.size.height)
        self._current_view().focus()

    def _text_input_focused(self) -> bool:
        return isinstance(self.focused, (Input, TextArea))

    def _navigation_allowed(self) -> bool:
        return not self._text_input_focused() and not CommandPalette.is_open(
            cast(App[object], self)
        )

    def action_navigate_down(self) -> None:
        if not self._navigation_allowed():
            return
        focused = self.focused
        if isinstance(focused, NavigationRail):
            focused.action_cursor_down()
        elif isinstance(focused, OptionList):
            focused.action_cursor_down()
        elif focused is not None:
            scroll_down = getattr(focused, "action_scroll_down", None)
            if callable(scroll_down):
                scroll_down()

    def action_navigate_up(self) -> None:
        if not self._navigation_allowed():
            return
        focused = self.focused
        if isinstance(focused, NavigationRail):
            focused.action_cursor_up()
        elif isinstance(focused, OptionList):
            focused.action_cursor_up()
        elif focused is not None:
            scroll_up = getattr(focused, "action_scroll_up", None)
            if callable(scroll_up):
                scroll_up()

    def action_navigate_left(self) -> None:
        if not self._navigation_allowed():
            return
        if (
            self.current_destination is Destination.MODELS
            and self.query_one(ModelsView).detail_open
        ):
            self.query_one(ModelsView).close_detail()
            return
        if (
            self.current_destination is Destination.HISTORY
            and self.query_one(HistoryView).detail_open
        ):
            self.query_one(HistoryView).close_detail()
            return
        if (
            self.current_destination is Destination.DOCTOR
            and self.query_one(DoctorView).detail_open
        ):
            self.query_one(DoctorView).close_detail()
            return
        if (
            self.current_destination is Destination.SETTINGS
            and self.query_one(SettingsView).editor_open
        ):
            self.query_one(SettingsView).close_editor()
            return
        if (
            self.current_destination is Destination.SETTINGS
            and self.query_one(SettingsView).category_open
            and self.layout_mode in {LayoutMode.COMPACT, LayoutMode.CONSTRAINED}
        ):
            self.query_one(SettingsView).close_category()
            return
        if self.layout_mode in {LayoutMode.COMPACT, LayoutMode.CONSTRAINED}:
            self._open_destination_overlay()
        elif not isinstance(self.focused, NavigationRail):
            self.query_one(NavigationRail).focus()

    def action_navigate_right(self) -> None:
        if not self._navigation_allowed():
            return
        if isinstance(self.focused, NavigationRail):
            self._current_view().focus()
        elif self.current_destination is Destination.MODELS:
            options = self.query_one("#models-list", OptionList)
            if options.highlighted is not None:
                option = options.get_option_at_index(options.highlighted)
                self.query_one(ModelsView).select(option.id)
        elif self.current_destination is Destination.HISTORY:
            view = self.query_one(HistoryView)
            options = self.query_one("#history-list", OptionList)
            if options.highlighted is not None:
                view.select(options.highlighted)
        elif self.current_destination is Destination.DOCTOR:
            view = self.query_one(DoctorView)
            options = self.query_one("#doctor-list", OptionList)
            if options.highlighted is not None:
                view.select(options.highlighted)
        elif self.current_destination is Destination.SETTINGS:
            self.action_activate()

    def action_activate(self) -> None:
        if not self._navigation_allowed():
            return
        if isinstance(self.focused, NavigationRail):
            self.navigate(self.focused.highlighted_destination, focus_content=False)
        elif self.current_destination is Destination.OVERVIEW:
            self.navigate(Destination.ROUTE)
        elif isinstance(self.focused, Button):
            self.focused.press()
        elif self.current_destination is Destination.MODELS:
            self.action_navigate_right()
        elif self.current_destination in {Destination.HISTORY, Destination.DOCTOR}:
            self.action_navigate_right()
        elif self.current_destination is Destination.SETTINGS and isinstance(
            self.focused, OptionList
        ):
            options = self.focused
            if options.highlighted is None:
                return
            selected = options.get_option_at_index(options.highlighted).id
            if selected is None:
                return
            view = self.query_one(SettingsView)
            if options.id == "settings-categories":
                view.select_category(selected)
            elif options.id == "settings-fields":
                view.select_field(selected)

    def action_go_back(self) -> None:
        if self.current_destination is Destination.EXECUTE:
            if self.execute_view_model.active:
                self.run_worker(self._cancel_execution(), exit_on_error=False)
            else:
                self._reject_pending_approval()
                self.execute_view_model.clear()
                self._navigate_back()
            return
        if self.current_destination is Destination.MODELS:
            view = self.query_one(ModelsView)
            if isinstance(self.focused, Input):
                self.focused.value = ""
                view.focus_list()
                return
            if view.detail_open:
                view.close_detail()
                return
        if self.current_destination is Destination.HISTORY:
            view = self.query_one(HistoryView)
            if isinstance(self.focused, Input):
                self.focused.value = ""
                view.focus_list()
                return
            if view.detail_open:
                view.close_detail()
                return
        if (
            self.current_destination is Destination.DOCTOR
            and self.query_one(DoctorView).detail_open
        ):
            self.query_one(DoctorView).close_detail()
            return
        if self.current_destination is Destination.SETTINGS:
            view = self.query_one(SettingsView)
            if view.editor_open:
                view.close_editor()
                return
            if view.category_open and self.layout_mode in {
                LayoutMode.COMPACT,
                LayoutMode.CONSTRAINED,
            }:
                view.close_category()
                return
            if isinstance(self.focused, Input):
                self.focused.value = ""
                view.focus_categories()
                return
        if self._text_input_focused():
            self._current_view().focus()
            return
        self._navigate_back()

    def action_refresh(self) -> None:
        if not self._navigation_allowed():
            return
        if self.current_destination is Destination.MODELS:
            self._load_models()
            return
        if self.current_destination is Destination.DOCTOR:
            self._load_doctor()
            return
        if self.current_destination is Destination.USAGE:
            self._refresh_usage()
            return
        if self.current_destination is Destination.HISTORY:
            self._load_history()
            return
        if self.current_destination is not Destination.OVERVIEW:
            return
        if self.overview_view_model.active:
            return
        self.run_worker(
            self.overview_view_model.refresh(self._publish_overview),
            name="Overview refresh",
            group="overview-refresh",
            exit_on_error=False,
        )

    def action_context_help(self) -> None:
        if not self._navigation_allowed():
            return
        self._overlay_focus = self.focused
        self.push_screen(
            HelpOverlay(
                self.localizer,
                self.current_destination,
                compact=self.layout_mode in {LayoutMode.COMPACT, LayoutMode.CONSTRAINED},
            ),
            self._restore_overlay_focus,
        )

    def action_request_quit(self) -> None:
        if self._text_input_focused() or CommandPalette.is_open(cast(App[object], self)):
            return
        if (
            self.current_destination is Destination.SETTINGS
            and self.query_one(SettingsView).arm_discard()
        ):
            return
        if self.execute_view_model.active:
            self.push_screen(QuitExecutionOverlay(self.localizer), self._quit_execution_chosen)
        else:
            self.exit()

    def _quit_execution_chosen(self, cancel_and_quit: bool | None) -> None:
        if cancel_and_quit:
            self.run_worker(self._cancel_execution(quit_after=True), exit_on_error=False)

    def action_analyze_task(self) -> None:
        if self.route_view_model.active or self._analysis_pending:
            return
        self.route_view_model.set_task(self.query_one("#route-task", TextArea).text)
        self._analysis_pending = True
        self.run_worker(self._analyze_task(), group="route-analyze", exit_on_error=False)

    async def _analyze_task(self) -> None:
        view = self.query_one(RouteView)
        try:
            state = await self.route_view_model.analyze(view.update_state)
            view.update_state(state)
        finally:
            self._analysis_pending = False

    def action_toggle_details(self) -> None:
        if self.current_destination is Destination.ROUTE:
            self.query_one(RouteView).toggle_details(self.route_view_model.state)
        elif self.current_destination is Destination.MODELS:
            self.query_one(ModelsView).toggle_evidence()
        elif self.current_destination is Destination.USAGE:
            self.query_one(UsageView).toggle_details()

    def action_filter_local(self) -> None:
        if self.current_destination is Destination.MODELS:
            self.query_one(ModelsView).focus_filter()
        elif self.current_destination is Destination.HISTORY:
            self.query_one(HistoryView).focus_filter()
        elif self.current_destination is Destination.SETTINGS:
            self.query_one(SettingsView).focus_filter()

    def _load_usage(self) -> None:
        if self.usage_view_model is None or self._usage_pending or self.usage_view_model.active:
            return
        self._usage_pending = True
        self.run_worker(self._load_usage_worker(), group="usage-load", exit_on_error=False)

    async def _load_usage_worker(self) -> None:
        try:
            if self.usage_view_model is not None:
                await self.usage_view_model.load(self.query_one(UsageView).update_state)
        finally:
            self._usage_pending = False

    def _load_history(self) -> None:
        if (
            self.history_view_model is None
            or self._history_pending
            or self.history_view_model.active
        ):
            return
        self._history_pending = True
        self.run_worker(self._load_history_worker(), group="history-load", exit_on_error=False)

    async def _load_history_worker(self) -> None:
        try:
            if self.history_view_model is not None:
                await self.history_view_model.load(
                    self.query_one(HistoryView).update_state, limit=200
                )
        finally:
            self._history_pending = False

    def _refresh_usage(self) -> None:
        if self.overview_view_model.active or self._usage_pending or self._usage_refresh_pending:
            return
        self._usage_refresh_pending = True
        self.run_worker(self._refresh_usage_worker(), group="overview-refresh", exit_on_error=False)

    async def _refresh_usage_worker(self) -> None:
        try:
            await self.overview_view_model.refresh(self._publish_overview)
            self._load_usage()
        finally:
            self._usage_refresh_pending = False

    def _load_doctor(self) -> None:
        if self._doctor_pending or self.doctor_view_model.active:
            return
        self._doctor_pending = True
        self.run_worker(self._load_doctor_worker(), group="doctor-load", exit_on_error=False)

    async def _load_doctor_worker(self) -> None:
        try:
            await self.doctor_view_model.load(self.query_one(DoctorView).update_state)
        finally:
            self._doctor_pending = False

    def _save_settings(self) -> None:
        view = self.query_one(SettingsView)
        if self._settings_pending or not view.view_model.dirty:
            return
        self._settings_pending = True
        self.run_worker(self._save_settings_worker(), group="settings-save", exit_on_error=False)

    async def _save_settings_worker(self) -> None:
        try:
            saved = await self.settings_view_model.save()
            view = self.query_one(SettingsView)
            view.feedback_id = "settings.saved" if saved else None
            view.update_editor_state()
        finally:
            self._settings_pending = False

    def _load_models(self) -> None:
        if self.models_view_model.active or self._models_pending:
            return
        self._models_pending = True
        self.run_worker(self._load_models_worker(), group="models-load", exit_on_error=False)

    async def _load_models_worker(self) -> None:
        view = self.query_one(ModelsView)
        try:
            state = await self.models_view_model.load(view.update_state)
            view.update_state(state)
        finally:
            self._models_pending = False

    def _prepare_execution(self, *, dry_run: bool) -> None:
        if (
            self.route_view_model.state.context is None
            or self.execute_view_model.active
            or self._planning_pending
        ):
            return
        task = self.route_view_model.task.strip()
        self._planning_pending = True
        self.navigate(Destination.EXECUTE)
        self.run_worker(
            self._prepare_execution_worker(task, dry_run=dry_run),
            group="execute-plan",
            exit_on_error=False,
        )

    async def _prepare_execution_worker(self, task: str, *, dry_run: bool) -> None:
        view = self.query_one(ExecuteView)
        try:
            state = await self.execute_view_model.prepare(
                task, Path.cwd(), dry_run=dry_run, publish=view.update_state
            )
            context = self.route_view_model.state.context
            if (
                state.plan is not None
                and context is not None
                and (
                    state.plan.quota_snapshot_captured_at == context.snapshot_captured_at
                    and state.plan.binding_pool_id == context.budget_report.binding_pool_id
                )
            ):
                pool = next(
                    (
                        pool
                        for pool in context.budget_report.pools
                        if pool.pool_id == state.plan.binding_pool_id
                    ),
                    None,
                )
                view.quota_state = self.localizer.text(
                    f"state.{pool.state.value}" if pool is not None else "state.unknown"
                )
            else:
                view.quota_state = self.localizer.text("state.unknown")
            view.update_state(state)
            self._apply_size(self.size.width, self.size.height)
            if state.plan is not None and not state.plan.dry_run:
                view.focus_cancel()
        finally:
            self._planning_pending = False

    def _approve_execution(self) -> None:
        state = self.execute_view_model.state
        if self._approval_future is not None:
            if not self._approval_future.done() and self._pending_plan is not None:
                self._approval_future.set_result(True)
            self._approval_future = None
            self._pending_plan = None
            self.query_one(ExecuteView).update_state(self.execute_view_model.resume())
            return
        plan = state.plan
        if state.status != "ready" or plan is None or plan.dry_run or self._execution_pending:
            return
        self._approved_plan = plan
        self._execution_pending = True
        self.run_worker(self._run_execution(), group="execution", exit_on_error=False)

    async def _approve_candidate(self, candidate: ExecutionPlan) -> bool:
        if self._approved_plan is not None and candidate == self._approved_plan:
            self._approved_plan = None
            return True
        self._pending_plan = candidate
        self._approval_future = asyncio.get_running_loop().create_future()
        self.execute_view_model.awaiting_change(candidate)
        self.query_one(ExecuteView).show_candidate(candidate)
        try:
            return await self._approval_future
        finally:
            self._approval_future = None
            self._pending_plan = None

    async def _run_execution(self) -> None:
        view = self.query_one(ExecuteView)
        try:
            state = await self.execute_view_model.run(
                self._approve_candidate, publish=self._publish_execution
            )
            view.update_state(state)
        finally:
            self._approved_plan = None
            self._execution_pending = False
            self._update_chrome()

    def _publish_execution(self, state: ExecuteState) -> None:
        self.query_one(ExecuteView).update_state(state)
        self._update_chrome()

    def _reject_pending_approval(self) -> None:
        if self._approval_future is not None and not self._approval_future.done():
            self._approval_future.set_result(False)
        self._approved_plan = None

    async def _cancel_execution(self, *, quit_after: bool = False) -> None:
        self._reject_pending_approval()
        await self.execute_view_model.cancel()
        self.query_one(ExecuteView).update_state(self.execute_view_model.state)
        self._update_chrome()
        if quit_after:
            self.exit()
        else:
            self._navigate_back()

    def _open_destination_overlay(self) -> None:
        self._overlay_focus = self.focused
        self.push_screen(
            DestinationOverlay(self.localizer, self.current_destination),
            self._destination_chosen,
        )

    def _destination_chosen(self, destination: Destination | None) -> None:
        if destination is not None:
            self.navigate(destination)
        else:
            self._restore_overlay_focus(None)

    def _restore_overlay_focus(self, _result: object) -> None:
        previous = self._overlay_focus
        self._overlay_focus = None
        if previous is not None:
            previous.focus()
        else:
            self._current_view().focus()

    def command_available(self, command_id: str) -> bool:
        if command_id == "refresh":
            return (
                self.current_destination in {Destination.OVERVIEW, Destination.USAGE}
                and not self.overview_view_model.active
            )
        if command_id == "run_doctor":
            return not self.doctor_view_model.active
        if command_id == "details":
            return self.current_destination in {
                Destination.ROUTE,
                Destination.MODELS,
                Destination.USAGE,
            }
        if command_id == "analyze":
            return (
                self.current_destination is Destination.ROUTE
                and bool(self.route_view_model.task.strip())
                and not self.route_view_model.active
            )
        if command_id in {"dry_run", "open_plan"}:
            return (
                self.current_destination is Destination.ROUTE
                and self.route_view_model.state.context is not None
            )
        if command_id == "recommended_model":
            return self.route_view_model.state.context is not None
        return True

    def run_command(self, action_id: str) -> None:
        if action_id.startswith("navigate:"):
            self.navigate(Destination(action_id.partition(":")[2]))
        elif action_id.startswith("setting:"):
            self.navigate(Destination.SETTINGS)
            if self.current_destination is Destination.SETTINGS:
                self.query_one(SettingsView).deep_link(action_id.partition(":")[2])
        elif action_id == "refresh":
            self.action_refresh()
        elif action_id == "run_doctor":
            self.navigate(Destination.DOCTOR)
            self._load_doctor()
        elif action_id == "details":
            self.action_toggle_details()
        elif action_id == "analyze":
            self.action_analyze_task()
        elif action_id == "dry_run":
            self._prepare_execution(dry_run=True)
        elif action_id == "open_plan":
            self._prepare_execution(dry_run=False)
        elif action_id == "recommended_model":
            self.navigate(Destination.MODELS)
            context = self.route_view_model.state.context
            if context is not None:
                self.query_one(ModelsView).selected_id = context.recommendation.selected_model_id
        elif action_id == "help":
            self.action_context_help()
        elif action_id == "quit":
            self.action_request_quit()


async def _smoke(app: QuotaPilotApp, *, size: tuple[int, int]) -> int:
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        app.query_one(HeaderBar)
        app.query_one(OverviewView)
        app.query_one(RouteView)
        app.query_one(ExecuteView)
        app.query_one(ModelsView)
        app.query_one(UsageView)
        app.query_one(HistoryView)
        app.query_one(SettingsView)
        app.query_one(DoctorView)
        for destination in (
            Destination.USAGE,
            Destination.HISTORY,
            Destination.SETTINGS,
            Destination.DOCTOR,
        ):
            # Installed-wheel smoke opens the packaged widgets without I/O.
            app.query_one(ContentSwitcher).current = f"{destination.value}-view"
            await pilot.pause()
        app.query_one(ContextualFooter)
    return 0


def run_tui(
    *,
    smoke_test: bool = False,
    config_path: str | Path | None = None,
) -> int:
    """Build and run the TUI; smoke mode never accesses provider or database."""
    effective = load_effective_config(path=config_path)
    app = QuotaPilotApp(build_dependencies(effective), enable_startup=not smoke_test)
    if smoke_test:
        return asyncio.run(_smoke(app, size=(80, 24)))
    app.run(mouse=True)
    return 0


def main() -> None:
    raise SystemExit(run_tui())
