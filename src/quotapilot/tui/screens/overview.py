"""Real service-backed Overview presentation."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, VerticalScroll
from textual.widgets import Static

from quotapilot.providers.base import ProviderAuthentication, ProviderConnection
from quotapilot.tui.localization import Localizer
from quotapilot.tui.state import OverviewState


class OverviewView(VerticalScroll):
    can_focus = True

    def __init__(self, localizer: Localizer) -> None:
        super().__init__(id="overview-view", classes="destination-view")
        self._localizer = localizer
        self._state = OverviewState()

    def compose(self) -> ComposeResult:
        yield Static("", id="overview-pool", classes="screen-title")
        yield Static("", id="overview-progress")
        with Horizontal(id="overview-primary"):
            yield Static("", id="overview-remaining")
            yield Static("", id="overview-state")
        with Grid(id="overview-metrics"):
            yield Static("", id="overview-reset")
            yield Static("", id="overview-today")
            yield Static("", id="overview-pressure")
        yield Static("", classes="subtle-rule")
        yield Static(self._localizer.text("overview.suggested"), classes="section-title")
        yield Static(self._localizer.text("overview.route_cta"), id="overview-route")
        yield Static(self._localizer.text("overview.route_reason"), id="overview-route-reason")
        yield Static("", id="overview-freshness", classes="muted")
        yield Static("", id="overview-provider", classes="muted")
        yield Static("", id="overview-source", classes="muted")
        yield Static("", id="overview-message")

    def update_state(self, state: OverviewState) -> None:
        self._state = state
        unknown = self._localizer.text("value.unknown")
        self.query_one("#overview-pool", Static).update(
            state.pool_name or self._localizer.text("overview.weekly")
        )
        self.query_one("#overview-progress", Static).update(self._progress(state, unknown))
        self.query_one("#overview-remaining", Static).update(
            self._localizer.text(
                "overview.remaining",
                value=self._fraction(state.remaining_fraction, unknown),
            )
        )
        state_widget = self.query_one("#overview-state", Static)
        for css_class in (
            "state-very-under",
            "state-under",
            "state-on-track",
            "state-over",
            "state-critical",
            "state-unknown",
        ):
            state_widget.remove_class(css_class)
        state_widget.add_class(f"state-{state.budget_state.value.replace('_', '-')}")
        state_widget.update(self._localizer.text(f"state.{state.budget_state.value}"))
        self.query_one("#overview-reset", Static).update(
            self._localizer.text(
                "overview.reset",
                value=self._duration(state.reset_seconds, unknown),
            )
        )
        self.query_one("#overview-today", Static).update(
            self._localizer.text(
                "overview.today",
                value=self._fraction(state.today_budget_fraction, unknown, digits=1),
            )
        )
        self.query_one("#overview-pressure", Static).update(
            self._localizer.text(
                "overview.pressure",
                value=unknown if state.pressure is None else f"{state.pressure:.2f}",
            )
        )
        stale = self._localizer.text("value.stale_suffix") if state.stale else ""
        freshness_widget = self.query_one("#overview-freshness", Static)
        freshness_widget.set_class(state.stale, "state-stale")
        freshness_widget.update(
            self._localizer.text(
                "overview.snapshot",
                age=self._age(state.snapshot_age_seconds, unknown),
                stale=stale,
            )
        )
        self.query_one("#overview-provider", Static).update(
            self._localizer.text(
                "overview.provider",
                status=self._provider_label(state),
            )
        )
        source_text = (
            self._localizer.text("overview.using_persisted") if state.using_persisted_data else ""
        )
        self.query_one("#overview-source", Static).update(source_text)
        message = self._localizer.text(state.message_id) if state.message_id else ""
        self.query_one("#overview-message", Static).update(message)

    def _progress(self, state: OverviewState, unknown: str) -> str:
        if state.used_fraction is None:
            return unknown
        width = 30
        used = round(state.used_fraction * width)
        bar = "=" * used + "-" * (width - used)
        return self._localizer.text(
            "overview.used",
            value=f"[{bar}] {state.used_fraction:.0%}",
        )

    @staticmethod
    def _fraction(value: float | None, unknown: str, *, digits: int = 0) -> str:
        return unknown if value is None else f"{value:.{digits}%}"

    def _duration(self, seconds: int | None, unknown: str) -> str:
        if seconds is None:
            return unknown
        days, remainder = divmod(max(seconds, 0), 86_400)
        hours, remainder = divmod(remainder, 3_600)
        minutes = remainder // 60
        if days:
            return self._localizer.text("duration.days_hours", days=days, hours=hours)
        if hours:
            return self._localizer.text("duration.hours_minutes", hours=hours, minutes=minutes)
        return self._localizer.text("duration.minutes", minutes=minutes)

    def _age(self, seconds: float | None, unknown: str) -> str:
        if seconds is None:
            return unknown
        rounded = round(max(seconds, 0))
        days, remainder = divmod(rounded, 86_400)
        hours, remainder = divmod(remainder, 3_600)
        minutes = remainder // 60
        if days:
            return self._localizer.text("age.days_hours", days=days, hours=hours)
        if hours:
            return self._localizer.text("age.hours_minutes", hours=hours, minutes=minutes)
        return self._localizer.text("age.minutes", minutes=minutes)

    def _provider_label(self, state: OverviewState) -> str:
        if state.authentication is ProviderAuthentication.NOT_AUTHENTICATED:
            return self._localizer.text("provider.not_authenticated")
        if state.connection is ProviderConnection.UNAVAILABLE:
            return self._localizer.text("provider.unavailable")
        if state.connection is ProviderConnection.CONNECTED:
            return self._localizer.text("provider.connected")
        return self._localizer.text("provider.unknown")
