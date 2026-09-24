"""Phase 9.2B service-backed screens and safe interaction boundaries."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from textual.widgets import Button, Input, OptionList, Select, Static

from quotapilot.budget.engine import BudgetEngine
from quotapilot.config.loader import EffectiveConfig
from quotapilot.config.models import AppConfig, DatabaseConfig
from quotapilot.domain.account import AccountInfo
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.quota import QuotaPool
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.observability.doctor import DoctorCheck, DoctorReport, DoctorStatus
from quotapilot.tui.app import QuotaPilotApp
from quotapilot.tui.dependencies import build_dependencies
from quotapilot.tui.localization import Localizer
from quotapilot.tui.screens.doctor import DoctorView
from quotapilot.tui.screens.history import HistoryView
from quotapilot.tui.screens.settings import SettingsView
from quotapilot.tui.screens.usage import UsageView
from quotapilot.tui.state import Destination, ViewStatus
from quotapilot.tui.viewmodels.doctor import DoctorState
from quotapilot.tui.viewmodels.settings import SETTING_SPECS, SettingsViewModel
from quotapilot.tui.viewmodels.usage import UsageViewModel

NOW = datetime.now(UTC).replace(microsecond=0)
SECRET = "raw-account-secret-9b"


class Repo:
    def __init__(self, snapshots: tuple[UsageSnapshot, ...] = (), fail: bool = False) -> None:
        self.snapshots = snapshots
        self.fail = fail
        self.calls = 0

    async def list_snapshots(
        self, *, provider: str | None = None, limit: int = 100
    ) -> tuple[UsageSnapshot, ...]:
        self.calls += 1
        if self.fail:
            raise RuntimeError("private database detail")
        return self.snapshots[:limit]


class Doctor:
    def __init__(self, report: DoctorReport) -> None:
        self.report = report
        self.calls = 0

    async def run(self, *, now: datetime, live: bool = False) -> DoctorReport:
        assert not live
        self.calls += 1
        return self.report


def snapshot(
    *, used: float | None = 0.68, minutes_ago: int = 0, timing: bool = True
) -> UsageSnapshot:
    captured = NOW - timedelta(minutes=minutes_ago)
    return UsageSnapshot(
        account=AccountInfo(
            provider="openai-codex",
            account_id=SECRET,
            capabilities=CapabilitySet(models=()),
            observed_at=captured,
        ),
        quota_pools=(
            QuotaPool(
                id="weekly",
                provider="openai-codex",
                kind="unknown",
                scope="unknown",
                used_fraction=used,
                remaining_fraction=None if used is None else 1.0 - used,
                starts_at=captured - timedelta(days=3) if timing else None,
                resets_at=captured + timedelta(days=4) if timing else None,
                window_seconds=7 * 86400 if timing else None,
            ),
        ),
        quota_bindings=(),
        captured_at=captured,
    )


def effective(tmp_path: Path) -> EffectiveConfig:
    return EffectiveConfig(
        config=AppConfig(database=DatabaseConfig(path=str(tmp_path / "usage.db"))),
        sources={},
        path=tmp_path / "config.yaml",
        file_present=False,
    )


def app_with(
    tmp_path: Path, repo: Repo | None = None, doctor: Doctor | None = None, *, lang: str = "en"
) -> QuotaPilotApp:
    deps = build_dependencies(effective(tmp_path))
    if repo is not None:
        deps = replace(deps, repository=cast(Any, repo))
    if doctor is not None:
        deps = replace(deps, doctor_service=cast(Any, doctor))
    return QuotaPilotApp(deps, localizer=Localizer(lang), enable_startup=False)


@pytest.mark.asyncio
async def test_usage_projection_actual_expected_unknown_stale_and_no_snapshot() -> None:
    repo = Repo(
        (snapshot(), snapshot(used=0.6, minutes_ago=30), snapshot(used=0.5, minutes_ago=60))
    )
    vm = UsageViewModel(cast(Any, repo), BudgetEngine(), "openai-codex")
    state = await vm.load(lambda _state: None)
    assert state.status is ViewStatus.READY
    assert state.latest is not None
    assert state.latest.pool.actual_usage == 0.68
    assert state.latest.pool.expected_usage is not None
    assert state.forecast is not None
    repo.snapshots = (snapshot(used=None, timing=False),)
    state = await vm.load(lambda _state: None)
    assert state.latest is not None
    assert state.latest.pool.actual_usage is None
    assert state.latest.pool.expected_usage is None
    assert state.forecast is not None and not state.forecast.points
    repo.snapshots = (snapshot(minutes_ago=60),)
    state = await vm.load(lambda _state: None)
    assert state.latest is not None and state.latest.stale
    repo.snapshots = ()
    assert (await vm.load(lambda _state: None)).status is ViewStatus.EMPTY
    repo.fail = True
    assert (await vm.load(lambda _state: None)).status is ViewStatus.ERROR


@pytest.mark.asyncio
async def test_usage_history_pilot_filter_detail_privacy_and_compact(tmp_path: Path) -> None:
    repo = Repo((snapshot(), snapshot(used=0.55, minutes_ago=10)))
    app = app_with(tmp_path, repo)
    async with app.run_test(size=(80, 24)) as pilot:
        app.navigate(Destination.USAGE)
        await pilot.pause()
        usage = app.query_one(UsageView)
        assert "68.0%" in str(app.query_one("#usage-main", Static).render())
        usage.toggle_details()
        assert app.query_one("#usage-details", Static).display
        app.navigate(Destination.HISTORY)
        await pilot.pause()
        history = app.query_one(HistoryView)
        assert app.query_one("#history-list", OptionList).option_count == 2
        history.select(0)
        assert history.detail_open
        app.action_go_back()
        assert not history.detail_open
        app.query_one("#history-filter", Input).value = "no-match"
        await pilot.pause()
        assert app.query_one("#history-list", OptionList).option_count == 0
        history.set_section("execution")
        assert "not stored" in str(app.query_one("#history-message", Static).render())
        screen = str(pilot.app.screen)
        assert SECRET not in screen
        assert app.layout_mode.value == "compact"


@pytest.mark.asyncio
async def test_settings_strict_validation_save_deep_link_and_discard(tmp_path: Path) -> None:
    vm = SettingsViewModel(effective(tmp_path))
    reserve = next(spec for spec in SETTING_SPECS if spec.key == "budget.reserve_fraction")
    assert not vm.update(reserve, "1.2")
    assert not vm.dirty
    assert not vm.path.exists()
    assert vm.update(reserve, "0.2")
    assert vm.dirty
    assert await vm.save()
    assert vm.path.exists()
    assert "0.2" in vm.path.read_text()
    assert vm.update(reserve, "0.3")
    vm.discard()
    assert vm.draft.budget.reserve_fraction == 0.2
    app = app_with(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        app.run_command("setting:appearance.language")
        view = app.query_one(SettingsView)
        assert view.selected is not None and view.selected.key == "appearance.language"
        app.query_one("#settings-select", Select).value = "ja"
        assert view.stage()
        assert app.settings_view_model.dirty
        assert not view.editor_open
        app.action_go_back()
        assert app.current_destination is Destination.SETTINGS
        app.action_go_back()
        assert app.current_destination is Destination.SETTINGS
        app.action_go_back()
        assert not app.settings_view_model.dirty
        await pilot.pause()
        app.query_one("#settings-filter", Input).value = "reserve"
        await pilot.pause()
        assert app.query_one("#settings-categories", OptionList).option_count == 1
        assert view.category == "budget"


@pytest.mark.asyncio
async def test_doctor_offline_statuses_details_rerun_and_actions(tmp_path: Path) -> None:
    report = DoctorReport(
        checked_at=NOW,
        healthy=False,
        checks=tuple(
            DoctorCheck(
                name=name, status=status, message="Safe summary", remediation="Open settings"
            )
            for name, status in (
                ("database", DoctorStatus.PASS),
                ("authentication", DoctorStatus.WARN),
                ("model_profiles", DoctorStatus.FAIL),
                ("provider_capture", DoctorStatus.SKIP),
            )
        ),
    )
    doctor = Doctor(report)
    app = app_with(tmp_path, Repo(), doctor, lang="ja")
    async with app.run_test(size=(80, 24)) as pilot:
        app.navigate(Destination.DOCTOR)
        await pilot.pause()
        view = app.query_one(DoctorView)
        view.update_state(DoctorState(ViewStatus.READY, report))
        assert app.query_one("#doctor-list", OptionList).option_count == 4
        view.select(1)
        assert "WARN" in str(app.query_one("#doctor-detail", Static).render())
        assert "Codex 認証" in str(app.query_one("#doctor-detail", Static).render())
        app.action_go_back()
        assert not view.detail_open
        app.action_refresh()
        await pilot.pause()
        assert doctor.calls >= 1
        app.query_one("#doctor-open-settings", Button).press()
        await pilot.pause()
        assert app.current_destination is Destination.SETTINGS


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(80, 24), (100, 30), (140, 40)])
@pytest.mark.parametrize("lang", ["en", "ja"])
async def test_secondary_screen_size_language_theme_smoke(
    tmp_path: Path, size: tuple[int, int], lang: str
) -> None:
    app = app_with(tmp_path, Repo(), lang=lang)
    async with app.run_test(size=size) as pilot:
        for destination in (
            Destination.USAGE,
            Destination.HISTORY,
            Destination.SETTINGS,
            Destination.DOCTOR,
        ):
            app.navigate(destination)
            await pilot.pause()
            assert app.current_destination is destination
            assert app.query_one(f"#{destination.value}-view")


@pytest.mark.asyncio
async def test_real_persisted_usage_is_bounded_and_private(tmp_path: Path) -> None:
    from quotapilot.history.sqlite import SqliteSnapshotRepository

    repo = SqliteSnapshotRepository(tmp_path / "persisted.db")
    await repo.save_snapshot(snapshot())
    loaded = await repo.list_snapshots(provider="openai-codex", limit=1)
    assert len(loaded) == 1
    assert loaded[0].account.account_id != SECRET
    vm = UsageViewModel(repo, BudgetEngine(), "openai-codex")
    state = await vm.load(lambda _state: None, limit=1)
    assert state.latest is not None
    assert state.latest.pool.actual_usage == 0.68
    app = app_with(tmp_path, Repo(loaded))
    async with app.run_test(size=(100, 30)) as pilot:
        app.navigate(Destination.USAGE)
        await pilot.pause()
        assert SECRET not in app.export_screenshot()


@pytest.mark.asyncio
async def test_usage_refresh_reuses_overview_safe_path(tmp_path: Path) -> None:
    from quotapilot.tui.state import OverviewState

    app = app_with(tmp_path, Repo((snapshot(),)))
    calls = 0

    async def safe_refresh(publish: Any) -> bool:
        nonlocal calls
        calls += 1
        publish(OverviewState(message_id="overview.provider_unavailable"))
        return True

    cast(Any, app.overview_view_model).refresh = safe_refresh
    async with app.run_test(size=(80, 24)) as pilot:
        app.navigate(Destination.USAGE)
        await pilot.pause()
        app.action_refresh()
        await pilot.pause()
        assert calls == 1
        assert "Provider unavailable" in str(app.query_one("#usage-message", Static).render())


@pytest.mark.asyncio
async def test_settings_theme_and_boolean_use_strict_selectors(tmp_path: Path) -> None:
    app = app_with(tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        app.run_command("setting:appearance.tui_theme")
        view = app.query_one(SettingsView)
        selector = app.query_one("#settings-select", Select)
        selector.value = "light"
        assert view.stage()
        assert app.settings_view_model.draft.appearance.tui_theme.value == "light"
        view.deep_link("execution.require_fresh_budget")
        selector.value = "false"
        assert view.stage()
        assert not app.settings_view_model.draft.execution.require_fresh_budget
        app._save_settings()
        await pilot.pause()
        assert app.settings_view_model.saved.appearance.tui_theme.value == "light"
        assert app.theme_resolution.resolved.value == "dark"  # next launch only
        assert "tui_theme: light" in (tmp_path / "config.yaml").read_text()


@pytest.mark.asyncio
async def test_system_locale_resolves_japanese_secondary_screen(tmp_path: Path) -> None:
    from quotapilot.config import LanguagePreference

    app = QuotaPilotApp(
        build_dependencies(effective(tmp_path)),
        localizer=Localizer.from_preference(LanguagePreference.SYSTEM, system_locale="ja_JP"),
        enable_startup=False,
    )
    async with app.run_test(size=(80, 24)) as pilot:
        app.navigate(Destination.USAGE)
        await pilot.pause()
        assert "使用状況" in str(app.query_one("#usage-view .screen-title", Static).render())


@pytest.mark.asyncio
async def test_japanese_local_filters_accept_full_width_text(tmp_path: Path) -> None:
    app = app_with(tmp_path, Repo((snapshot(),)), lang="ja")
    async with app.run_test(size=(80, 24)) as pilot:
        app.navigate(Destination.HISTORY)
        await pilot.pause()
        app.query_one("#history-filter", Input).value = "危険"
        await pilot.pause()
        assert app.query_one("#history-list", OptionList).option_count == 1
        app.navigate(Destination.SETTINGS)
        app.query_one("#settings-filter", Input).value = "外観"
        await pilot.pause()
        assert app.query_one("#settings-categories", OptionList).option_count == 1
