"""Contextual help derived from the shared key registry."""

from __future__ import annotations

from rich.console import Group
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from quotapilot.tui.keymap import HelpGroup, help_specs
from quotapilot.tui.localization import Localizer
from quotapilot.tui.state import Destination


class HelpOverlay(ModalScreen[None]):
    BINDINGS = [
        Binding("escape,question_mark", "close_help", show=False, priority=True),
        Binding("q,r,slash", "noop", show=False, priority=True),
    ]

    def __init__(
        self,
        localizer: Localizer,
        destination: Destination,
        *,
        compact: bool,
    ) -> None:
        super().__init__(id="help-overlay")
        self._localizer = localizer
        self._destination = destination
        self._compact = compact

    def compose(self) -> ComposeResult:
        screen = self._localizer.text(f"destination.{self._destination.value}")
        parts: list[Text | Table] = [
            Text(self._localizer.text("help.title", screen=screen), style="bold"),
            Text(""),
        ]
        specs = help_specs(self._destination)
        for group in HelpGroup:
            rows = [spec for spec in specs if spec.help_group is group]
            if not rows:
                continue
            parts.append(Text(self._localizer.text(f"help.{group.value}"), style="bold"))
            table = Table.grid(padding=(0, 3))
            table.add_column(no_wrap=True)
            table.add_column()
            for spec in rows:
                description_id = (
                    "help.menu"
                    if self._compact and spec.action == "navigate_left"
                    else spec.description_id
                )
                table.add_row(spec.key_display, self._localizer.text(description_id))
            parts.extend((table, Text("")))
        parts.append(Text(self._localizer.text("help.close"), style="dim"))
        with Vertical(id="help-dialog"):
            yield Static(Group(*parts), id="help-content")

    def action_close_help(self) -> None:
        self.dismiss(None)

    def action_noop(self) -> None:
        return
