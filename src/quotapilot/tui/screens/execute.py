"""Inspect, approve, and observe controlled execution."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Static

from quotapilot.execution.models import ExecutionPlan, ExecutionStatus
from quotapilot.tui.localization import Localizer
from quotapilot.tui.viewmodels.execute import ExecuteState


class ExecuteView(VerticalScroll):
    can_focus = True

    def __init__(self, localizer: Localizer) -> None:
        super().__init__(id="execute-view", classes="destination-view")
        self._localizer = localizer
        self.quota_state = localizer.text("value.unknown")

    def compose(self) -> ComposeResult:
        yield Static(self._localizer.text("destination.execute"), classes="screen-title")
        yield Static("", id="execute-message", classes="notice")
        with Vertical(id="execute-plan"):
            yield Static(self._localizer.text("execute.plan"), classes="section-title")
            yield Static("", id="execute-fields")
            yield Static(self._localizer.text("route.escalation"), classes="section-title")
            yield Static("", id="execute-escalation")
            yield Static(self._localizer.text("execute.warning"), id="execute-warning")
            with Horizontal(id="execute-actions", classes="action-row"):
                yield Button(self._localizer.text("execute.cancel"), id="execute-cancel")
                yield Button(self._localizer.text("execute.approve"), id="execute-approve")
                yield Button(self._localizer.text("execute.back_route"), id="execute-back-route")
            yield Static("", id="execute-result")

    def on_mount(self) -> None:
        self.update_state(ExecuteState())

    def focus_cancel(self) -> None:
        self.query_one("#execute-cancel", Button).focus()

    def update_state(self, state: ExecuteState) -> None:
        if not self.is_mounted:
            return
        plan = state.plan
        self.query_one("#execute-plan", Vertical).display = plan is not None
        messages = {
            "empty": "execute.empty",
            "planning": "execute.planning",
            "running": "execute.running",
            "cancelled": "execute.cancelled",
        }
        message_id = state.message_id or messages.get(state.status)
        message = self._localizer.text(message_id) if message_id else ""
        if state.status == "running" and plan is not None:
            message = self._localizer.text(
                "execute.running_attempt",
                number=plan.attempt_number,
                maximum=plan.max_attempts,
            )
        message_widget = self.query_one("#execute-message", Static)
        message_widget.set_class(state.status == "error", "semantic-error")
        message_widget.update(Text(message))
        if plan is None:
            return
        self._render_plan(plan)
        dry_run = plan.dry_run
        running = state.status == "running"
        self.query_one("#execute-approve", Button).display = (
            not dry_run and not running and state.result is None
        )
        self.query_one("#execute-cancel", Button).display = not dry_run and state.result is None
        self.query_one("#execute-back-route", Button).display = dry_run or state.result is not None
        result_widget = self.query_one("#execute-result", Static)
        result = state.result
        result_widget.display = result is not None
        if result is not None:
            duration = max(0, round((result.finished_at - result.started_at).total_seconds()))
            status_id = f"execute.status.{result.status.value}"
            status = self._localizer.text(status_id)
            output = "\n".join(filter(None, (result.stdout_summary, result.stderr_summary)))
            lines = [
                f"{self._localizer.text('execute.status')}: {status}",
                f"{self._localizer.text('execute.model')}: {result.model_id}",
                f"{self._localizer.text('execute.attempts')}: {result.attempt_count}",
                f"{self._localizer.text('execute.duration')}: {duration}s",
            ]
            if result.failure_class is not None:
                lines.append(
                    f"{self._localizer.text('execute.failure')}: {result.failure_class.value}"
                )
            if output:
                lines.extend((self._localizer.text("execute.output"), output))
            result_text = Text("\n".join(lines))
            # Color only the outcome label; output and plan details stay neutral.
            if result.status in {ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED}:
                prefix = f"{self._localizer.text('execute.status')}: "
                outcome_color = (
                    self.app.current_theme.success
                    if result.status is ExecutionStatus.SUCCEEDED
                    else self.app.current_theme.error
                )
                if outcome_color is not None:
                    result_text.stylize(outcome_color, len(prefix), len(prefix) + len(status))
            result_widget.update(result_text)

    def _render_plan(self, plan: ExecutionPlan) -> None:
        unknown = self._localizer.text("value.unknown")
        approval = self._localizer.text(
            "execute.approval_required" if plan.requires_confirmation else "execute.ui_approval"
        )
        pressure = unknown if plan.budget_pressure is None else f"{plan.budget_pressure:.2f}"
        quota = f"{self.quota_state} · {pressure}"
        labels = (
            ("execute.model", plan.model_id),
            ("execute.effort", plan.effort or unknown),
            ("execute.directory", str(plan.working_directory)),
            ("execute.quota", quota),
            ("execute.approval", approval),
            ("execute.timeout", f"{plan.timeout_seconds}s"),
            ("execute.attempts", str(plan.max_attempts)),
        )
        prefix = self._localizer.text("execute.dry_run") + "\n" if plan.dry_run else ""
        self.query_one("#execute-fields", Static).update(
            Text(
                prefix + "\n".join(f"{self._localizer.text(key)}  {value}" for key, value in labels)
            )
        )
        escalation = "\n".join(
            f"{i}. {step.model_id} · {step.effort or unknown}"
            for i, step in enumerate(plan.escalation_path, start=1)
        ) or self._localizer.text("route.no_escalation")
        self.query_one("#execute-escalation", Static).update(Text(escalation))
        self.query_one("#execute-warning", Static).display = not plan.dry_run

    def show_candidate(self, plan: ExecutionPlan) -> None:
        self._render_plan(plan)
        self.query_one("#execute-message", Static).update(
            Text(self._localizer.text("execute.changed_plan"))
        )
        self.query_one("#execute-approve", Button).display = True
        self.query_one("#execute-cancel", Button).display = True
        self.focus_cancel()
