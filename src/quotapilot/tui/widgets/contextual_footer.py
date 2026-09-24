"""Compact contextual discoverability footer."""

from __future__ import annotations

from textual.widgets import Static

from quotapilot.tui.keymap import footer_specs
from quotapilot.tui.localization import Localizer
from quotapilot.tui.state import Destination


class ContextualFooter(Static):
    def __init__(self, localizer: Localizer) -> None:
        super().__init__("", id="contextual-footer")
        self._localizer = localizer

    def update_context(
        self,
        destination: Destination,
        *,
        navigation_focused: bool,
        compact: bool,
    ) -> None:
        specs = footer_specs(
            destination,
            navigation_focused=navigation_focused,
            compact=compact,
        )
        labels: list[str] = []
        seen: set[str] = set()
        for spec in specs:
            group = spec.footer_group or spec.action
            if spec.footer_id is None or group in seen:
                continue
            seen.add(group)
            message_id = spec.footer_id
            if (
                destination is Destination.OVERVIEW
                and spec.action == "activate"
                and not compact
                and not navigation_focused
            ):
                message_id = "footer.route"
            if compact and spec.action == "navigate_left":
                message_id = "footer.menu"
            labels.append(self._localizer.text(message_id))
        self.update("   ".join(labels[:6]))
