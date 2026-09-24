"""Phase 9.1 TUI state, interaction, localization, and safety coverage."""

from __future__ import annotations

import asyncio
import io
import json
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from rich.cells import cell_len
from rich.console import Console
from textual.command import CommandPalette
from textual.widgets import Input, Static, TextArea
from typer.testing import CliRunner

from quotapilot.budget.models import BudgetState
from quotapilot.capabilities.models import ProfileFreshness
from quotapilot.cli.app import app as cli_app
from quotapilot.config import TuiThemePreference, load_effective_config
from quotapilot.observability.models import (
    ProfileStatus,
    SnapshotSource,
    StatusPool,
    StatusReport,
)
from quotapilot.providers.base import (
    ProviderAuthentication,
    ProviderConnection,
    ProviderInspection,
)
from quotapilot.providers.openai_codex.provider import OpenAICodexProvider
from quotapilot.services.provider_status import ProviderStatusService
from quotapilot.services.status import StatusService
from quotapilot.tui.app import QuotaPilotApp
from quotapilot.tui.commands import COMMANDS
from quotapilot.tui.dependencies import TuiDependencies
from quotapilot.tui.localization import (
    Localizer,
    load_catalog,
    truncate_cells,
    validate_catalogs,
)
from quotapilot.tui.screens.help import HelpOverlay
from quotapilot.tui.screens.overview import OverviewView
from quotapilot.tui.state import (
    Destination,
    LayoutMode,
    VerticalMode,
    ViewStatus,
    horizontal_mode,
    map_overview_state,
    vertical_mode,
)
from quotapilot.tui.theme import QUOTAPILOT_THEMES, resolve_theme
from quotapilot.tui.viewmodels.overview import OverviewViewModel
from quotapilot.tui.widgets.navigation import DestinationOverlay, NavigationRail

NOW = datetime(2026, 9, 23, 12, tzinfo=UTC)
runner = CliRunner()


def _report(
    *,
    source: SnapshotSource = SnapshotSource.PERSISTED,
    stale: bool = False,
    unknown: bool = False,
) -> StatusReport:
    captured = NOW - timedelta(minutes=18) if stale else NOW
    return StatusReport(
        provider="openai-codex",
        source=source,
        captured_at=captured,
        evaluated_at=NOW,
        snapshot_age_seconds=1080.0 if stale else 0.0,
        is_stale=stale,
        pools=(
            StatusPool(
                pool_id="private-internal-pool",
                name="Weekly",
                state=BudgetState.UNKNOWN if unknown else BudgetState.OVER,
                used_fraction=None if unknown else 0.68,
                remaining_fraction=None if unknown else 0.32,
                today_budget_fraction=None if unknown else 0.053,
                resets_at=NOW + timedelta(days=4, hours=8),
            ),
        ),
        effective_pressure=None if unknown else 0.43,
        binding_pool_id="private-internal-pool",
        profile=ProfileStatus(
            evaluated_on=date(2026, 9, 23),
            freshness=ProfileFreshness.FRESH,
            model_count=4,
            routable_model_count=2,
            profiled_model_count=2,
        ),
    )


class _FakeProvider:
    def __init__(
        self,
        *,
        connection: ProviderConnection = ProviderConnection.CONNECTED,
        authentication: ProviderAuthentication = ProviderAuthentication.AUTHENTICATED,
    ) -> None:
        self.connection = connection
        self.authentication = authentication

    async def inspect_status(self) -> ProviderInspection:
        return ProviderInspection(
            provider="openai-codex",
            connection=self.connection,
            authentication=self.authentication,
            checked_at=NOW,
        )

    async def capture_usage(self) -> Any:
        raise AssertionError("fake StatusService owns refresh behavior")


class _FakeStatusService:
    def __init__(
        self,
        local: StatusReport | None = None,
        live: StatusReport | None = None,
        *,
        fail_refresh: bool = False,
        delay_refresh: bool = False,
    ) -> None:
        self.local = local
        self.live = live
        self.fail_refresh = fail_refresh
        self.delay_refresh = delay_refresh
        self.local_calls = 0
        self.refresh_calls = 0
        self.refresh_started = asyncio.Event()
        self.release_refresh = asyncio.Event()

    async def get_status(self, **kwargs: Any) -> StatusReport | None:
        if kwargs.get("refresh_provider") is None:
            self.local_calls += 1
            return self.local
        self.refresh_calls += 1
        self.refresh_started.set()
        if self.delay_refresh:
            await self.release_refresh.wait()
        if self.fail_refresh:
            raise RuntimeError("raw secret provider failure")
        return self.live


def _dependencies(
    tmp_path: Path,
    *,
    language: str = "en",
    theme: str = "system",
    service: _FakeStatusService | None = None,
    provider: _FakeProvider | None = None,
) -> TuiDependencies:
    config = tmp_path / f"{language}-{theme}.yaml"
    config.write_text(
        f"appearance:\n  language: {language}\n  tui_theme: {theme}\n",
        encoding="utf-8",
    )
    effective = load_effective_config(path=config, environ={})
    return TuiDependencies(
        effective=effective,
        provider=cast(OpenAICodexProvider, provider or _FakeProvider()),
        provider_status_service=ProviderStatusService(),
        status_service=cast(StatusService, service or _FakeStatusService()),
    )


def _app(
    tmp_path: Path,
    *,
    language: str = "en",
    theme: str = "system",
    service: _FakeStatusService | None = None,
    provider: _FakeProvider | None = None,
    enable_startup: bool = False,
) -> QuotaPilotApp:
    localizer = Localizer(language)
    return QuotaPilotApp(
        _dependencies(
            tmp_path,
            language=language,
            theme=theme,
            service=service,
            provider=provider,
        ),
        localizer=localizer,
        enable_startup=enable_startup,
    )


def test_state_mapping_preserves_unknown_stale_and_privacy() -> None:
    state = map_overview_state(
        _report(stale=True, unknown=True),
        None,
        status=ViewStatus.READY,
    )

    assert state.remaining_fraction is None
    assert state.today_budget_fraction is None
    assert state.pressure is None
    assert state.budget_state is BudgetState.UNKNOWN
    assert state.stale is True
    serialized = json.dumps(state.__dict__ if hasattr(state, "__dict__") else str(state))
    assert "account_id" not in serialized
    assert "token" not in serialized
    assert "raw_observation" not in serialized


@pytest.mark.asyncio
async def test_startup_publishes_persisted_before_one_safe_live_refresh() -> None:
    service = _FakeStatusService(
        _report(),
        _report(source=SnapshotSource.LIVE_CAPTURE),
        delay_refresh=True,
    )
    view_model = OverviewViewModel(
        cast(StatusService, service),
        ProviderStatusService(),
        cast(OpenAICodexProvider, _FakeProvider()),
        selected_provider="openai-codex",
        clock=lambda: NOW,
    )
    published = []

    task = asyncio.create_task(view_model.startup(published.append))
    await service.refresh_started.wait()

    assert any(state.source is SnapshotSource.PERSISTED for state in published)
    persisted_index = next(
        index for index, state in enumerate(published) if state.source is SnapshotSource.PERSISTED
    )
    refreshing_index = next(index for index, state in enumerate(published) if state.refreshing)
    assert persisted_index < refreshing_index
    assert service.local_calls == 1
    assert service.refresh_calls == 1

    service.release_refresh.set()
    await task
    assert published[-1].source is SnapshotSource.LIVE_CAPTURE
    assert published[-1].refreshing is False


@pytest.mark.asyncio
async def test_refresh_failure_preserves_persisted_and_coalesces_duplicates() -> None:
    service = _FakeStatusService(
        _report(stale=True),
        None,
        fail_refresh=True,
        delay_refresh=True,
    )
    view_model = OverviewViewModel(
        cast(StatusService, service),
        ProviderStatusService(),
        cast(OpenAICodexProvider, _FakeProvider()),
        selected_provider="openai-codex",
        clock=lambda: NOW,
    )
    published = []

    task = asyncio.create_task(view_model.startup(published.append))
    await service.refresh_started.wait()
    assert await view_model.refresh(published.append) is False
    service.release_refresh.set()
    await task

    assert service.refresh_calls == 1
    assert published[-1].source is SnapshotSource.PERSISTED
    assert published[-1].stale is True
    assert published[-1].message_id == "overview.refresh_failed"


@pytest.mark.asyncio
async def test_status_service_fallback_result_is_labeled_refresh_failure() -> None:
    service = _FakeStatusService(
        _report(),
        _report(source=SnapshotSource.PERSISTED_FALLBACK, stale=True),
    )
    view_model = OverviewViewModel(
        cast(StatusService, service),
        ProviderStatusService(),
        cast(OpenAICodexProvider, _FakeProvider()),
        selected_provider="openai-codex",
        clock=lambda: NOW,
    )
    published = []

    await view_model.startup(published.append)

    assert published[-1].source is SnapshotSource.PERSISTED_FALLBACK
    assert published[-1].stale is True
    assert published[-1].message_id == "overview.refresh_failed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("connection", "authentication", "message_id"),
    [
        (
            ProviderConnection.CONNECTED,
            ProviderAuthentication.NOT_AUTHENTICATED,
            "overview.not_authenticated",
        ),
        (
            ProviderConnection.UNAVAILABLE,
            ProviderAuthentication.UNKNOWN,
            "overview.provider_unavailable",
        ),
        (
            ProviderConnection.UNKNOWN,
            ProviderAuthentication.UNKNOWN,
            "overview.provider_unknown",
        ),
    ],
)
async def test_unsafe_startup_state_skips_provider_refresh(
    connection: ProviderConnection,
    authentication: ProviderAuthentication,
    message_id: str,
) -> None:
    service = _FakeStatusService(_report(), _report(source=SnapshotSource.LIVE_CAPTURE))
    view_model = OverviewViewModel(
        cast(StatusService, service),
        ProviderStatusService(),
        cast(
            OpenAICodexProvider,
            _FakeProvider(connection=connection, authentication=authentication),
        ),
        selected_provider="openai-codex",
        clock=lambda: NOW,
    )
    published = []

    await view_model.startup(published.append)

    assert service.refresh_calls == 0
    assert published[-1].source is SnapshotSource.PERSISTED
    assert published[-1].message_id == message_id


def test_localization_catalogs_fallback_and_cell_width() -> None:
    validate_catalogs()
    english = load_catalog("en")
    japanese = load_catalog("ja")
    assert english.keys() == japanese.keys()
    assert Localizer("ja").text("destination.overview") == "概要"
    assert Localizer("ja").text("missing.message") == "missing.message"

    sample = "日本語e\u0301abcdef"
    truncated = truncate_cells(sample, 8)
    assert cell_len(truncated) <= 8
    assert truncated.endswith("…")


def test_breakpoints_and_theme_resolution() -> None:
    assert horizontal_mode(140) is LayoutMode.WIDE
    assert horizontal_mode(120) is LayoutMode.WIDE
    assert horizontal_mode(119) is LayoutMode.STANDARD
    assert horizontal_mode(88) is LayoutMode.STANDARD
    assert horizontal_mode(80) is LayoutMode.COMPACT
    assert horizontal_mode(60) is LayoutMode.COMPACT
    assert horizontal_mode(59) is LayoutMode.CONSTRAINED
    assert vertical_mode(30) is VerticalMode.NORMAL
    assert vertical_mode(24) is VerticalMode.SHORT
    assert vertical_mode(18) is VerticalMode.VERY_SHORT
    assert vertical_mode(17) is VerticalMode.UNSAFE

    system = resolve_theme(TuiThemePreference.SYSTEM)
    assert system.resolved is TuiThemePreference.DARK
    assert system.used_fallback is True
    assert resolve_theme(TuiThemePreference.DARK).textual_name == "quotapilot-dark"
    assert resolve_theme(TuiThemePreference.LIGHT).textual_name == "quotapilot-light"
    assert {theme.name for theme in QUOTAPILOT_THEMES} == {
        "quotapilot-system",
        "quotapilot-dark",
        "quotapilot-light",
    }


@pytest.mark.parametrize(
    (
        "name",
        "background",
        "surface",
        "accent",
        "subtle",
        "focus",
        "success",
        "warning",
        "error",
        "stale",
    ),
    [
        (
            "quotapilot-dark",
            "#08111B",
            "#0D1724",
            "#4F6FD6",
            "#15213A",
            "#708DE3",
            "#4fa873",
            "#d6a657",
            "#df6b72",
            "#b58b49",
        ),
        (
            "quotapilot-light",
            "#F5F7FB",
            "#FFFFFF",
            "#334E9E",
            "#E8EDF9",
            "#526EC2",
            "#176b43",
            "#8a5b00",
            "#a4252d",
            "#76531a",
        ),
    ],
)
def test_tui_theme_separates_navy_interaction_from_semantic_colors(
    name: str,
    background: str,
    surface: str,
    accent: str,
    subtle: str,
    focus: str,
    success: str,
    warning: str,
    error: str,
    stale: str,
) -> None:
    theme = next(theme for theme in QUOTAPILOT_THEMES if theme.name == name)
    assert (theme.background, theme.surface, theme.primary, theme.accent) == (
        background,
        surface,
        accent,
        accent,
    )
    assert theme.variables["accent-subtle"] == subtle
    assert theme.variables["accent-focus"] == focus
    assert theme.variables["block-cursor-background"] == subtle
    assert theme.variables["input-selection-background"] == subtle
    assert theme.success == success
    assert theme.warning == warning
    assert theme.error == error
    assert theme.variables["stale"] == stale
    assert theme.variables["muted"] != accent  # UNKNOWN stays neutral.
    assert all(
        theme.variables[key] != success
        for key in ("accent-hover", "accent-pressed", "accent-subtle", "accent-focus")
    )


def test_system_theme_uses_the_exact_dark_palette() -> None:
    system, dark = QUOTAPILOT_THEMES[:2]
    assert system.variables == dark.variables
    for field in (
        "primary",
        "secondary",
        "warning",
        "error",
        "success",
        "accent",
        "foreground",
        "background",
        "surface",
        "panel",
        "dark",
    ):
        assert getattr(system, field) == getattr(dark, field)


@pytest.mark.asyncio
async def test_overview_stale_and_over_keep_semantic_styles(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        app.query_one(OverviewView).update_state(
            map_overview_state(_report(stale=True), None, status=ViewStatus.READY)
        )
        assert app.query_one("#overview-freshness", Static).has_class("state-stale")
        assert app.query_one("#overview-state", Static).has_class("state-over")


@pytest.mark.asyncio
async def test_standard_arrow_hjkl_enter_escape_and_focus(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        navigation = app.query_one(NavigationRail)
        assert app.layout_mode is LayoutMode.STANDARD
        assert app.focused is navigation

        await pilot.press("down")
        assert navigation.highlighted == 1
        await pilot.press("up", "j")
        assert navigation.highlighted == 1
        await pilot.press("k", "j", "enter")
        assert app.current_destination is Destination.ROUTE

        await pilot.press("escape")
        assert app.current_destination is Destination.OVERVIEW
        await pilot.press("tab")
        assert app.focused is navigation
        await pilot.press("shift+tab")
        assert isinstance(app.focused, OverviewView)
        await pilot.press("l")
        assert isinstance(app.focused, OverviewView)
        await pilot.press("h")
        assert app.focused is navigation


@pytest.mark.asyncio
async def test_text_input_keeps_printable_hjklq_and_question_mark(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        field = Input(id="focus-test-input")
        await app.query_one(OverviewView).mount(field)
        field.focus()
        await pilot.press("h", "j", "k", "l", "q", "question_mark", "slash", "r")
        await pilot.pause()

        assert field.value == "hjklq?/r"
        assert app.is_running
        assert app.current_destination is Destination.OVERVIEW

        editor = TextArea(id="focus-test-text-area")
        await app.query_one(OverviewView).mount(editor)
        editor.focus()
        await pilot.press("h", "j", "k", "l", "q")
        assert editor.text == "hjklq"
        assert app.is_running
        await pilot.press("ctrl+p")
        await pilot.pause()
        assert CommandPalette.is_open(cast(Any, app))
        await pilot.press("escape")
        assert app.focused is editor


@pytest.mark.asyncio
async def test_manual_r_refreshes_once_and_q_quits_navigation(tmp_path: Path) -> None:
    service = _FakeStatusService(None, _report(source=SnapshotSource.LIVE_CAPTURE))
    app = _app(tmp_path, service=service)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        assert service.refresh_calls == 1
        assert app.query_one(OverviewView)._state.source is SnapshotSource.LIVE_CAPTURE

        await pilot.press("q")
        await pilot.pause()
        assert app.is_running is False


@pytest.mark.asyncio
async def test_help_is_contextual_modal_and_does_not_leak_q(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpOverlay)

        renderable = app.screen.query_one("#help-content", Static).content
        console = Console(record=True, width=80, file=io.StringIO())
        console.print(renderable)
        help_text = console.export_text()
        assert "Help - Overview" in help_text
        assert "refresh quota" in help_text
        assert "Ctrl+P" in help_text

        await pilot.press("q")
        assert isinstance(app.screen, HelpOverlay)
        await pilot.press("question_mark")
        assert not isinstance(app.screen, HelpOverlay)
        assert isinstance(app.focused, NavigationRail)


@pytest.mark.asyncio
async def test_localized_command_palette_navigates_and_restores_focus(tmp_path: Path) -> None:
    app = _app(tmp_path, language="ja")
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        opener = app.focused
        await pilot.press("ctrl+p")
        await pilot.pause()
        assert CommandPalette.is_open(cast(Any, app))
        await pilot.press("診", "断")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        assert app.current_destination is Destination.DOCTOR
        assert app.focused is not opener
        assert {command.id for command in COMMANDS} >= {
            "overview",
            "route",
            "execute",
            "usage",
            "models",
            "history",
            "settings",
            "doctor",
            "refresh",
            "help",
            "quit",
        }


@pytest.mark.asyncio
async def test_command_palette_escape_restores_prior_focus(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        opener = app.focused
        await pilot.press("ctrl+p")
        await pilot.pause()
        assert CommandPalette.is_open(cast(Any, app))
        await pilot.press("escape")
        await pilot.pause()
        assert CommandPalette.is_open(cast(Any, app)) is False
        assert app.focused is opener


@pytest.mark.asyncio
async def test_compact_overlay_and_live_resize(tmp_path: Path) -> None:
    app = _app(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.layout_mode is LayoutMode.COMPACT
        assert isinstance(app.focused, OverviewView)
        assert app.query_one("#navigation").display is False

        await pilot.press("left")
        await pilot.pause()
        assert isinstance(app.screen, DestinationOverlay)
        await pilot.press("down", "enter")
        await pilot.pause()
        assert app.current_destination is Destination.ROUTE

        await pilot.resize_terminal(120, 30)
        await pilot.pause()
        assert app.layout_mode is LayoutMode.WIDE
        assert app.current_destination is Destination.ROUTE
        assert app.query_one("#navigation").display is True

        await pilot.resize_terminal(59, 17)
        await pilot.pause()
        assert app.layout_mode is LayoutMode.CONSTRAINED
        assert app.vertical_mode is VerticalMode.UNSAFE
        assert app.query_one("#resize-guard").display is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("size", "expected"),
    [
        ((140, 40), LayoutMode.WIDE),
        ((120, 30), LayoutMode.WIDE),
        ((100, 30), LayoutMode.STANDARD),
        ((88, 24), LayoutMode.STANDARD),
        ((80, 24), LayoutMode.COMPACT),
        ((72, 20), LayoutMode.COMPACT),
        ((60, 18), LayoutMode.COMPACT),
    ],
)
@pytest.mark.parametrize("language", ["en", "ja"])
async def test_acceptance_sizes_have_no_primary_horizontal_overflow(
    tmp_path: Path,
    size: tuple[int, int],
    expected: LayoutMode,
    language: str,
) -> None:
    app = _app(tmp_path, language=language)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        assert app.layout_mode is expected
        view = app.query_one(OverviewView)
        assert view.region.x >= 0
        assert view.region.right <= size[0]
        assert app.query_one("#contextual-footer", Static).region.right <= size[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("preference", "textual_name", "resolved"),
    [
        ("system", "quotapilot-system", TuiThemePreference.DARK),
        ("dark", "quotapilot-dark", TuiThemePreference.DARK),
        ("light", "quotapilot-light", TuiThemePreference.LIGHT),
    ],
)
async def test_theme_smoke_keeps_focus_visible(
    tmp_path: Path,
    preference: str,
    textual_name: str,
    resolved: TuiThemePreference,
) -> None:
    app = _app(tmp_path, theme=preference)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.theme == textual_name
        assert app.theme_resolution.resolved is resolved
        assert app.focused is not None


def test_tui_cli_help_non_tty_smoke_and_lazy_import() -> None:
    help_result = runner.invoke(cli_app, ["--help"])
    bare_result = runner.invoke(cli_app, [])
    tui_help = runner.invoke(cli_app, ["tui", "--help"])
    non_tty = runner.invoke(cli_app, ["tui"])
    smoke = runner.invoke(cli_app, ["tui", "--smoke-test"])

    assert help_result.exit_code == 0 and "tui" in help_result.output
    assert bare_result.exit_code != 0 and "Usage" in bare_result.output
    assert tui_help.exit_code == 0
    assert non_tty.exit_code == 2
    assert "requires an interactive terminal" in non_tty.output
    assert "\x1b" not in non_tty.output
    assert smoke.exit_code == 0, smoke.output

    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import quotapilot.cli.app; print('textual' in sys.modules)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert probe.stdout.strip() == "False"
