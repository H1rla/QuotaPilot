"""Adaptive destination navigation."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from quotapilot.tui.localization import Localizer
from quotapilot.tui.state import DESTINATIONS, Destination


class NavigationRail(OptionList):
    def __init__(self, localizer: Localizer, *, id: str = "navigation") -> None:
        self._localizer = localizer
        self._destination = Destination.OVERVIEW
        super().__init__(
            *(self._option(destination) for destination in DESTINATIONS),
            id=id,
        )
        self.highlighted = 0

    def _option(self, destination: Destination) -> Option:
        marker = ">" if destination is self._destination else " "
        return Option(
            f"{marker} {self._localizer.text(f'destination.{destination.value}')}",
            id=destination.value,
        )

    def set_destination(self, destination: Destination) -> None:
        self._destination = destination
        index = DESTINATIONS.index(destination)
        for option_index, item in enumerate(DESTINATIONS):
            self.replace_option_prompt_at_index(option_index, self._option(item).prompt)
        self.highlighted = index

    @property
    def highlighted_destination(self) -> Destination:
        index = self.highlighted if self.highlighted is not None else 0
        return DESTINATIONS[index]


class DestinationOverlay(ModalScreen[Destination | None]):
    BINDINGS = [
        Binding("escape,h,left", "cancel", show=False, priority=True),
        Binding("q,r,slash", "noop", show=False, priority=True),
    ]

    def __init__(self, localizer: Localizer, current: Destination) -> None:
        super().__init__(id="destination-overlay")
        self._localizer = localizer
        self._current = current

    def compose(self) -> ComposeResult:
        rail = NavigationRail(self._localizer, id="destination-menu")
        rail.set_destination(self._current)
        yield rail

    def on_mount(self) -> None:
        self.query_one(NavigationRail).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id is not None:
            self.dismiss(Destination(event.option.id))

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_noop(self) -> None:
        return
