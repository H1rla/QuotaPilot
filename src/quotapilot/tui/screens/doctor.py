"""Compact list/detail over canonical offline Doctor checks."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from quotapilot.observability.doctor import DoctorCheck, DoctorStatus
from quotapilot.tui.localization import Localizer
from quotapilot.tui.state import ViewStatus
from quotapilot.tui.viewmodels.doctor import DoctorState


class DoctorView(VerticalScroll):
    can_focus = True

    def __init__(self, localizer: Localizer) -> None:
        super().__init__(id="doctor-view", classes="destination-view")
        self._localizer = localizer
        self._state = DoctorState()
        self.detail_open = False
        self.compact = True

    def compose(self) -> ComposeResult:
        yield Static(self._localizer.text("destination.doctor"), classes="screen-title")
        yield Static("", id="doctor-message", classes="notice")
        yield OptionList(id="doctor-list")
        yield Static("", id="doctor-summary", classes="muted")
        yield Static("", id="doctor-detail")
        with Horizontal(classes="action-row", id="doctor-actions"):
            yield Button(self._localizer.text("doctor.settings"), id="doctor-open-settings")
            yield Button(self._localizer.text("doctor.models"), id="doctor-open-models")

    def on_mount(self) -> None:
        self.update_state(self._state)

    def set_compact(self, compact: bool) -> None:
        self.compact = compact
        if self.is_mounted:
            self._render_state()

    def focus_list(self) -> None:
        self.query_one("#doctor-list", OptionList).focus()

    def update_state(self, state: DoctorState) -> None:
        self._state = state
        if self.is_mounted:
            self._render_state()

    def select(self, index: int) -> None:
        report = self._state.report
        if report is None or not 0 <= index < len(report.checks):
            return
        self.query_one("#doctor-list", OptionList).highlighted = index
        self.detail_open = True
        self._render_state()

    def close_detail(self) -> None:
        self.detail_open = False
        self._render_state()
        self.focus_list()

    def _render_state(self) -> None:
        t = self._localizer.text
        report = self._state.report
        message = self._state.message_id or (
            "doctor.running" if self._state.status is ViewStatus.LOADING else None
        )
        self.query_one("#doctor-message", Static).update(t(message) if message else "")
        options = self.query_one("#doctor-list", OptionList)
        previous = options.highlighted
        options.clear_options()
        checks = report.checks if report else ()
        for index, check in enumerate(checks):
            name = t(f"doctor.check.{check.name}")
            prompt = Text(f"{check.status.value}  ·  {name}")
            token = {
                DoctorStatus.PASS: "success",
                DoctorStatus.WARN: "warning",
                DoctorStatus.FAIL: "error",
                DoctorStatus.SKIP: "muted",
            }[check.status]
            color = (
                self.app.current_theme.variables["muted"]
                if token == "muted"
                else getattr(self.app.current_theme, token)
            )
            prompt.stylize(color, 0, len(check.status.value))
            options.add_option(Option(prompt, id=str(index)))
        if checks:
            options.highlighted = min(previous or 0, len(checks) - 1)
        summary = (
            ""
            if report is None
            else t(
                "doctor.summary",
                count=len(checks),
                warnings=sum(c.status is DoctorStatus.WARN for c in checks),
                failures=sum(c.status is DoctorStatus.FAIL for c in checks),
            )
        )
        resolution = getattr(self.app, "theme_resolution", None)
        if report is not None and resolution is not None and resolution.used_fallback:
            summary += "\n" + t("settings.system_fallback")
        self.query_one("#doctor-summary", Static).update(summary)
        detail = self.query_one("#doctor-detail", Static)
        detail.display = self.detail_open and bool(checks)
        options.display = not self.detail_open or not self.compact
        if detail.display:
            check: DoctorCheck = checks[min(options.highlighted or 0, len(checks) - 1)]
            reason = check.message
            remediation = check.remediation
            if self._localizer.language == "ja":
                reason_key = f"doctor.reason.{check.name}.{check.status.value.lower()}"
                translated = t(reason_key)
                if translated != reason_key:
                    reason = translated
                action_key = f"doctor.remediation.{check.name}"
                translated_action = t(action_key)
                if remediation is not None and translated_action != action_key:
                    remediation = translated_action
            detail.update(
                "\n".join(
                    (
                        f"{t(f'doctor.check.{check.name}')} — {check.status.value}",
                        reason,
                        f"{t('doctor.action')}: {remediation}" if remediation else "",
                    )
                )
            )
        else:
            detail.update("")
