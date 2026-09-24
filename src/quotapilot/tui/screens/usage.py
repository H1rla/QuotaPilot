"""Actual versus expected quota pace, with optional bounded trend."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from quotapilot.tui.localization import Localizer
from quotapilot.tui.state import ViewStatus
from quotapilot.tui.viewmodels.usage import UsageState

_SPARK = "▁▂▃▄▅▆▇█"


class UsageView(VerticalScroll):
    can_focus = True

    def __init__(self, localizer: Localizer) -> None:
        super().__init__(id="usage-view", classes="destination-view")
        self._localizer = localizer
        self._state = UsageState()
        self.details_open = False
        self.compact = True
        self.provider_message_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Static(self._localizer.text("destination.usage"), classes="screen-title")
        yield Static("", id="usage-message", classes="notice")
        yield Static("", id="usage-main")
        yield Static("", id="usage-trend", classes="muted")
        yield Static("", id="usage-details", classes="muted")

    def on_mount(self) -> None:
        self.update_state(self._state)

    def set_compact(self, compact: bool) -> None:
        self.compact = compact
        if self.is_mounted:
            self.update_state(self._state)

    def toggle_details(self) -> None:
        self.details_open = not self.details_open
        self.update_state(self._state)

    def update_state(self, state: UsageState) -> None:
        self._state = state
        if not self.is_mounted:
            return
        t = self._localizer.text
        latest = state.latest
        message = (
            state.message_id
            or self.provider_message_id
            or ("usage.loading" if state.status is ViewStatus.LOADING else None)
        )
        self.query_one("#usage-message", Static).update(t(message) if message else "")
        main = self.query_one("#usage-main", Static)
        if latest is None:
            main.update(t("usage.no_snapshot"))
            self.query_one("#usage-trend", Static).update("")
            self.query_one("#usage-details", Static).update("")
            return
        pool = latest.pool
        unknown = t("value.unknown")

        def pct(value: float | None) -> str:
            return unknown if value is None else f"{value:.1%}"

        delta = unknown if pool.pace_delta is None else f"{pool.pace_delta:+.1%}"
        reset = (
            unknown
            if pool.time_until_reset_seconds is None
            else t("usage.reset_time", hours=pool.time_until_reset_seconds // 3600)
        )
        lines = [
            pool.pool_name or t("overview.weekly"),
            f"{t('usage.actual')}     {pct(pool.actual_usage)}",
            f"{t('usage.expected')}   {pct(pool.expected_usage)}",
            f"{t('usage.delta')}      {delta}",
            f"{t('usage.state')}      {t(f'state.{pool.state.value}')}",
            f"{t('usage.reset')}      {reset}",
        ]
        if latest.stale:
            lines.append(t("usage.stale"))
        lines.append(t("overview.using_persisted"))
        body = Text("\n".join(lines))
        state_label = t(f"state.{pool.state.value}")
        state_start = body.plain.find(state_label)
        semantic = {
            "over": "warning",
            "critical": "error",
            "unknown": "muted",
        }.get(pool.state.value)
        if semantic and state_start >= 0:
            color = (
                self.app.current_theme.variables["muted"]
                if semantic == "muted"
                else getattr(self.app.current_theme, semantic)
            )
            body.stylize(
                color,
                state_start,
                state_start + len(state_label),
            )
        if latest.stale:
            stale_label = t("usage.stale")
            stale_start = body.plain.find(stale_label)
            body.stylize(
                self.app.current_theme.variables["stale"],
                stale_start,
                stale_start + len(stale_label),
            )
        main.update(body)
        trend = state.trend
        chart = (
            ""
            if self.compact or len(trend) < 3
            else "".join(_SPARK[min(7, max(0, round(value * 7)))] for value in trend)
        )
        self.query_one("#usage-trend", Static).update(
            t("usage.trend", chart=chart) if chart else ""
        )
        details = ""
        if self.details_open:
            captured = latest.captured_at.astimezone().strftime("%Y-%m-%d %H:%M")
            pressure = unknown if pool.pressure is None else f"{pool.pressure:.2f}"
            source = pool.timing_source.value if pool.timing_source else unknown
            details = "\n".join(
                (
                    t("usage.details"),
                    f"{t('usage.captured')}: {captured}",
                    f"{t('usage.pressure')}: {pressure}",
                    f"{t('usage.source')}: {source}",
                )
            )
        self.query_one("#usage-details", Static).update(details)
