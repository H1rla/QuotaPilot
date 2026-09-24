"""Safe quit confirmation while an execution worker owns a process."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from quotapilot.tui.localization import Localizer


class QuitExecutionOverlay(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "continue_execution", show=False, priority=True)]

    def __init__(self, localizer: Localizer) -> None:
        super().__init__(id="quit-execution-overlay")
        self._localizer = localizer

    def compose(self) -> ComposeResult:
        with Vertical(id="quit-execution-dialog"):
            yield Static(self._localizer.text("execute.quit_warning"))
            with Horizontal(classes="action-row"):
                yield Button(self._localizer.text("execute.continue"), id="quit-continue")
                yield Button(self._localizer.text("execute.cancel_quit"), id="quit-cancel")

    def on_mount(self) -> None:
        self.query_one("#quit-continue", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "quit-cancel")

    def action_continue_execution(self) -> None:
        self.dismiss(False)
