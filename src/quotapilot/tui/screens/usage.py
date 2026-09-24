"""Quota summary and left-to-right daily forecast strip."""

from __future__ import annotations

from rich.cells import set_cell_size
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static

from quotapilot.tui.localization import Localizer
from quotapilot.tui.state import ViewStatus
from quotapilot.tui.viewmodels.usage import UsageState


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
        yield Static("", id="usage-forecast")
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
            self.query_one("#usage-forecast", Static).update(t("usage.forecast_unavailable"))
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
        forecast = state.forecast
        if forecast is None or not forecast.points:
            reason = (
                forecast.unavailable_reason.value
                if forecast and forecast.unavailable_reason
                else ""
            )
            explanation = (
                t("usage.insufficient_evidence")
                if reason in {"insufficient_evidence", "incompatible_window"}
                else t("usage.forecast_unavailable")
            )
            forecast_text = Text(t("usage.forecast_title") + "\n" + explanation)
            if forecast is not None and forecast.stale:
                forecast_text.append(
                    "\n" + t("usage.forecast_stale"),
                    style=self.app.current_theme.variables["stale"],
                )
        else:
            forecast_text = self._render_forecast(state)
        self.query_one("#usage-forecast", Static).update(forecast_text)
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
            if forecast is not None and forecast.points:
                details += "\n" + t("usage.forecast_basis")
                for point in forecast.points:
                    details += (
                        "\n"
                        + point.date.isoformat()
                        + f"  {t('usage.projected')} {point.projected_used_fraction:.0%}"
                        + f"  {t('usage.expected')} {point.expected_used_fraction:.0%}"
                        + f"  {t('usage.delta')} {point.delta_from_expected:+.0%}"
                        + f"  {t('usage.remaining')} {point.projected_remaining_fraction:.0%}"
                    )
        self.query_one("#usage-details", Static).update(details)

    def _render_forecast(self, state: UsageState) -> Text:
        forecast = state.forecast
        assert forecast is not None
        t = self._localizer.text
        result = Text(t("usage.forecast_title") + "\n")
        if forecast.stale:
            result.append(
                t("usage.forecast_stale") + "\n", style=self.app.current_theme.variables["stale"]
            )
        points = forecast.points
        # One row at standard widths; at 80 columns the second chronological
        # group starts below the first without terminal horizontal scrolling.
        available = max(20, self.size.width)
        cell_width = 10
        per_row = 4 if self.compact else max(1, min(7, (available + 1) // (cell_width + 1)))
        weekdays = (
            "usage.mon",
            "usage.tue",
            "usage.wed",
            "usage.thu",
            "usage.fri",
            "usage.sat",
            "usage.sun",
        )
        for start in range(0, len(points), per_row):
            group = points[start : start + per_row]
            if start:
                result.append("\n")
            for field in ("day", "value", "state"):
                for index, point in enumerate(group):
                    if index:
                        result.append(" ")
                    if field == "day":
                        value = (
                            t("usage.today")
                            if point.is_today
                            else t(weekdays[point.date.weekday()])
                        )
                    elif field == "value":
                        value = f"{point.projected_used_fraction:.0%}"
                    else:
                        value = t(f"state.{point.state.value}")
                    color = None
                    if field == "state":
                        if point.state.value == "over":
                            color = self.app.current_theme.warning
                        elif point.state.value == "critical":
                            color = self.app.current_theme.error
                        elif point.state.value == "unknown":
                            color = self.app.current_theme.variables["muted"]
                    result.append(set_cell_size(value, cell_width), style=color)
                result.append("\n")
        return result
