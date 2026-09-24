"""Shared forecast presentation boundaries and responsive screen rendering."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from textual.content import Content
from textual.widgets import Static

from quotapilot.budget.engine import BudgetEngine
from quotapilot.budget.forecast import DailyForecast, DailyForecastPoint, ForecastUnavailable
from quotapilot.budget.models import BudgetState, PoolBudgetAssessment
from quotapilot.config.loader import EffectiveConfig
from quotapilot.config.models import AppConfig, DatabaseConfig
from quotapilot.domain.account import AccountInfo
from quotapilot.domain.capability import CapabilitySet
from quotapilot.domain.quota import QuotaPool
from quotapilot.domain.usage import UsageSnapshot
from quotapilot.gui.mappers import map_daily_forecast
from quotapilot.gui.viewmodels.usage import UsageViewModel as GuiUsageViewModel
from quotapilot.tui.app import QuotaPilotApp
from quotapilot.tui.dependencies import build_dependencies
from quotapilot.tui.localization import Localizer
from quotapilot.tui.screens.usage import UsageView
from quotapilot.tui.state import Destination, ViewStatus
from quotapilot.tui.viewmodels.usage import UsageSample, UsageState
from quotapilot.tui.viewmodels.usage import UsageViewModel as TuiUsageViewModel

NOW = datetime(2026, 9, 25, 12, tzinfo=UTC)


def synthetic_forecast(values: tuple[float, ...], *, stale: bool = False) -> DailyForecast:
    points = tuple(
        DailyForecastPoint(
            date=date(2026, 9, 25) + timedelta(days=index), is_today=index == 0,
            projected_used_fraction=value, projected_remaining_fraction=1 - value,
            expected_used_fraction=.4 + index * .1,
            delta_from_expected=value - (.4 + index * .1),
            state=(BudgetState.CRITICAL if value >= 1 else
                   BudgetState.OVER if value >= .75 else BudgetState.ON_TRACK),
            exceeds_raw_quota=value > 1, ends_at_reset=index == len(values) - 1,
        ) for index, value in enumerate(values)
    )
    return DailyForecast(NOW, "today_observed_pace", "persisted", stale, points)


def usage_state(forecast: DailyForecast) -> UsageState:
    pool = PoolBudgetAssessment(
        pool_id="weekly", actual_usage=.4, expected_usage=.39,
        pace_delta=.01, state=BudgetState.ON_TRACK,
        time_until_reset_seconds=3600 * 72,
    )
    return UsageState(
        ViewStatus.READY, (UsageSample(NOW, pool, forecast.stale),), forecast=forecast,
    )


def app_for(tmp_path: Path, language: str) -> QuotaPilotApp:
    effective = EffectiveConfig(
        config=AppConfig(database=DatabaseConfig(path=str(tmp_path / "ui.db"))),
        sources={}, path=tmp_path / "config.yaml", file_present=False,
    )
    return QuotaPilotApp(build_dependencies(effective), localizer=Localizer(language),
                         enable_startup=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(140, 40), (100, 30), (80, 24)])
@pytest.mark.parametrize("language", ["en", "ja"])
async def test_tui_forecast_horizontal_chronology_and_details(
    tmp_path: Path, size: tuple[int, int], language: str,
) -> None:
    app = app_for(tmp_path, language)
    async with app.run_test(size=size) as pilot:
        app.navigate(Destination.USAGE)
        await pilot.pause()
        view = app.query_one(UsageView)
        view.update_state(usage_state(synthetic_forecast((.43, .51, .59, .67, 1.05, 1.16, 1.23))))
        body = app.query_one("#usage-forecast", Static).render()
        assert isinstance(body, Content)
        rendered = body.plain
        assert "105%" in rendered and "116%" in rendered
        assert ("Today" if language == "en" else "今日") in rendered
        lines = rendered.splitlines()
        assert ("Today" if language == "en" else "今日") in lines[1]
        assert ("Sat" if language == "en" else "土") in lines[1]
        if size[0] == 80:
            assert len(lines) > 5
        else:
            assert len(lines) == 4
        view.toggle_details()
        assert "2026-09-25" in str(app.query_one("#usage-details", Static).render())
        assert "usage-trend" not in {widget.id for widget in view.query("Static")}


def test_gui_mapping_preserves_overrun_and_state() -> None:
    mapped = map_daily_forecast(synthetic_forecast((.43, 1.16)))
    assert mapped[0]["projectedText"] == "43%"
    assert mapped[1]["projectedText"] == "116%"
    assert mapped[1]["statusValue"] == "CRITICAL"
    assert mapped[1]["remainingText"] == "-16%"


@pytest.mark.asyncio
@pytest.mark.parametrize("evidence", [False, True])
async def test_gui_tui_viewmodels_receive_identical_forecast(evidence: bool) -> None:
    def snapshot(at: datetime, used: float) -> UsageSnapshot:
        return UsageSnapshot(
            account=AccountInfo(provider="test", account_id=None,
                                capabilities=CapabilitySet(models=()), observed_at=at),
            quota_pools=(QuotaPool(
                id="weekly", provider="test", kind="rolling", scope="account",
                used_fraction=used, starts_at=NOW - timedelta(days=2),
                resets_at=NOW + timedelta(days=4),
            ),),
            quota_bindings=(), captured_at=at,
        )

    rows = (snapshot(NOW, .4),)
    if evidence:
        rows += (snapshot(NOW - timedelta(hours=2), .38),)

    class Repo:
        async def list_snapshots(self, **_kwargs: Any) -> tuple[UsageSnapshot, ...]:
            return rows

    class Runner:
        def start(self, factory: Any, success: Any, failure: Any) -> None:
            import asyncio

            try:
                success(asyncio.run(factory()))
            except Exception as exc:  # noqa: BLE001 - mirrors GUI runner
                failure(exc)

    repository = cast(Any, Repo())
    budget = BudgetEngine()
    dependencies = SimpleNamespace(
        repository=repository, budget_engine=budget,
        effective=SimpleNamespace(config=SimpleNamespace(
            provider=SimpleNamespace(default="test")
        )),
    )
    # The GUI runner owns an event loop; run it outside this async test loop.
    import asyncio

    gui = await asyncio.to_thread(
        lambda: _load_gui_usage(dependencies, Runner())
    )
    tui = TuiUsageViewModel(repository, budget, "test", clock=lambda: NOW)
    state = await tui.load(lambda _state: None)
    assert state.forecast is not None
    assert gui.forecastReason == (
        state.forecast.unavailable_reason.value if state.forecast.unavailable_reason else ""
    )
    assert gui.forecastStale == state.forecast.stale
    assert gui.points == map_daily_forecast(state.forecast)


def _load_gui_usage(dependencies: Any, runner: Any) -> GuiUsageViewModel:
    gui = GuiUsageViewModel(cast(Any, dependencies), cast(Any, runner), clock=lambda: NOW)
    gui.load()
    return gui


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", ["quotapilot-dark", "quotapilot-light"])
@pytest.mark.parametrize("no_color", [False, True])
async def test_tui_forecast_resize_stale_unavailable_and_color_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, theme: str, no_color: bool,
) -> None:
    if no_color:
        monkeypatch.setenv("NO_COLOR", "1")
    else:
        monkeypatch.delenv("NO_COLOR", raising=False)
    app = app_for(tmp_path, "en")
    app.theme = theme
    async with app.run_test(size=(140, 40)) as pilot:
        app.navigate(Destination.USAGE)
        await pilot.pause()
        view = app.query_one(UsageView)
        view.update_state(usage_state(
            synthetic_forecast((.61, .72, .83, .94, 1.05, 1.16), stale=True)
        ))
        forecast = app.query_one("#usage-forecast", Static).render()
        assert isinstance(forecast, Content)
        assert "STALE" in forecast.plain and "105%" in forecast.plain
        assert "OVER" in forecast.plain and "CRITICAL" in forecast.plain
        assert len(forecast.plain.splitlines()) == 5
        await pilot.resize_terminal(80, 24)
        forecast = app.query_one("#usage-forecast", Static).render()
        assert isinstance(forecast, Content)
        assert len(forecast.plain.splitlines()) > 5
        await pilot.resize_terminal(100, 30)
        forecast = app.query_one("#usage-forecast", Static).render()
        assert isinstance(forecast, Content)
        assert len(forecast.plain.splitlines()) == 5
        unavailable = DailyForecast(
            NOW, "today_observed_pace", "persisted", False,
            unavailable_reason=ForecastUnavailable.INSUFFICIENT_EVIDENCE,
        )
        view.update_state(usage_state(unavailable))
        forecast = app.query_one("#usage-forecast", Static).render()
        assert isinstance(forecast, Content)
        assert "Insufficient data" in forecast.plain
