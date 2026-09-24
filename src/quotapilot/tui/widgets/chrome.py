"""One-row application header."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from quotapilot.providers.base import ProviderAuthentication, ProviderConnection
from quotapilot.tui.localization import Localizer
from quotapilot.tui.state import Destination


class HeaderBar(Horizontal):
    def __init__(self, localizer: Localizer) -> None:
        super().__init__(id="header-bar")
        self._localizer = localizer

    def compose(self) -> ComposeResult:
        yield Static("", id="header-title")
        yield Static("", id="header-provider")

    def update_header(
        self,
        destination: Destination,
        connection: ProviderConnection,
        authentication: ProviderAuthentication,
        *,
        executing: bool = False,
    ) -> None:
        title = self._localizer.text(f"destination.{destination.value}")
        self.query_one("#header-title", Static).update(
            self._localizer.text("app.title", destination=title)
        )
        if authentication is ProviderAuthentication.NOT_AUTHENTICATED:
            message_id = "header.not_authenticated"
        elif connection is ProviderConnection.UNAVAILABLE:
            message_id = "header.unavailable"
        elif connection is ProviderConnection.CONNECTED:
            message_id = "header.connected"
        else:
            message_id = "header.unknown"
        self.query_one("#header-provider", Static).update(
            self._localizer.text("header.executing")
            if executing
            else self._localizer.text(message_id)
        )
