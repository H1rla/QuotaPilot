"""Privacy-safe usage list/detail and honest empty execution history."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option

from quotapilot.tui.localization import Localizer
from quotapilot.tui.state import ViewStatus
from quotapilot.tui.viewmodels.usage import UsageSample, UsageState


class HistoryView(VerticalScroll):
    can_focus = True

    def __init__(self, localizer: Localizer) -> None:
        super().__init__(id="history-view", classes="destination-view")
        self._localizer = localizer
        self._state = UsageState()
        self.section = "usage"
        self.detail_open = False
        self.compact = True
        self._visible: tuple[UsageSample, ...] = ()

    def compose(self) -> ComposeResult:
        yield Static(self._localizer.text("destination.history"), classes="screen-title")
        with Horizontal(classes="action-row"):
            yield Button(self._localizer.text("history.usage"), id="history-usage-tab")
            yield Button(self._localizer.text("history.execution"), id="history-execution-tab")
        yield Input(placeholder=self._localizer.text("history.filter"), id="history-filter")
        yield Static("", id="history-message", classes="notice")
        yield OptionList(id="history-list")
        yield Static("", id="history-detail")

    def on_mount(self) -> None:
        self.update_state(self._state)

    def set_compact(self, compact: bool) -> None:
        self.compact = compact
        if self.is_mounted:
            self._render_state()

    def focus_list(self) -> None:
        self.query_one("#history-list", OptionList).focus()

    def focus_filter(self) -> None:
        self.query_one("#history-filter", Input).focus()

    def set_section(self, section: str) -> None:
        self.section = section
        self.detail_open = False
        self._render_state()

    def update_state(self, state: UsageState) -> None:
        self._state = state
        if self.is_mounted:
            self._render_state()

    def select(self, index: int) -> None:
        if 0 <= index < len(self._visible):
            self.query_one("#history-list", OptionList).highlighted = index
            self.detail_open = True
            self._render_detail()

    def close_detail(self) -> None:
        self.detail_open = False
        self._render_detail()
        self.focus_list()

    def _render_state(self) -> None:
        t = self._localizer.text
        usage = self.section == "usage"
        self.query_one("#history-list", OptionList).display = usage and (
            not self.detail_open or not self.compact
        )
        self.query_one("#history-filter", Input).display = usage
        message = ""
        if not usage:
            message = t("history.execution_empty")
        elif self._state.status is ViewStatus.LOADING:
            message = t("history.loading")
        elif self._state.message_id:
            message = t(self._state.message_id)
        self.query_one("#history-message", Static).update(message)
        query = self.query_one("#history-filter", Input).value.casefold().strip()
        self._visible = (
            tuple(
                sample
                for sample in self._state.samples
                if query in self._search_text(sample).casefold()
            )
            if usage
            else ()
        )
        options = self.query_one("#history-list", OptionList)
        previous = options.highlighted
        options.clear_options()
        for index, sample in enumerate(self._visible):
            actual = (
                t("value.unknown")
                if sample.pool.actual_usage is None
                else f"{sample.pool.actual_usage:.0%}"
            )
            state = t(f"state.{sample.pool.state.value}")
            stamp = sample.captured_at.astimezone().strftime("%m-%d %H:%M")
            prompt = Text(f"{stamp}  {actual}  {state}")
            token = {
                "over": "warning",
                "critical": "error",
                "unknown": "muted",
            }.get(sample.pool.state.value)
            if token:
                color = (
                    self.app.current_theme.variables["muted"]
                    if token == "muted"
                    else getattr(self.app.current_theme, token)
                )
                prompt.stylize(color, len(prompt.plain) - len(state), len(prompt.plain))
            options.add_option(Option(prompt, id=str(index)))
        if self._visible:
            options.highlighted = min(previous or 0, len(self._visible) - 1)
        self._render_detail()

    def _search_text(self, sample: UsageSample) -> str:
        pool = sample.pool
        return " ".join(
            (
                sample.captured_at.astimezone().strftime("%Y-%m-%d %H:%M"),
                pool.pool_name or "",
                pool.state.value,
                self._localizer.text(f"state.{pool.state.value}"),
            )
        )

    def _render_detail(self) -> None:
        detail = self.query_one("#history-detail", Static)
        detail.display = self.detail_open and self.section == "usage"
        if not detail.display or not self._visible:
            detail.update("")
            return
        index = self.query_one("#history-list", OptionList).highlighted or 0
        sample = self._visible[min(index, len(self._visible) - 1)]
        t = self._localizer.text
        pool = sample.pool

        def fmt(value: float | None) -> str:
            return t("value.unknown") if value is None else f"{value:.1%}"

        pressure = t("value.unknown") if pool.pressure is None else f"{pool.pressure:.2f}"
        detail.update(
            "\n".join(
                (
                    sample.captured_at.astimezone().strftime("%Y-%m-%d %H:%M"),
                    f"{t('usage.actual')}: {fmt(pool.actual_usage)}",
                    f"{t('usage.expected')}: {fmt(pool.expected_usage)}",
                    f"{t('usage.delta')}: {fmt(pool.pace_delta)}",
                    f"{t('usage.state')}: {t(f'state.{pool.state.value}')}",
                    f"{t('usage.pressure')}: {pressure}",
                    t("usage.stale") if sample.stale else t("history.fresh"),
                )
            )
        )
