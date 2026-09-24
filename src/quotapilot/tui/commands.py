"""Stable localized commands for Textual's fuzzy command palette."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, cast

from textual.command import DiscoveryHit, Hit, Hits, Provider

from quotapilot.tui.localization import Localizer
from quotapilot.tui.state import DESTINATIONS, Destination


@dataclass(frozen=True, slots=True)
class CommandDescriptor:
    id: str
    title_message_id: str
    help_message_id: str
    action_id: str
    keywords: tuple[str, ...] = ()


DESTINATION_COMMANDS: tuple[CommandDescriptor, ...] = tuple(
    CommandDescriptor(
        id=destination.value,
        title_message_id=f"command.{destination.value}.title",
        help_message_id=f"command.{destination.value}.help",
        action_id=f"navigate:{destination.value}",
        keywords=(destination.value, "open", "navigation"),
    )
    for destination in DESTINATIONS
)

COMMANDS: tuple[CommandDescriptor, ...] = DESTINATION_COMMANDS + (
    CommandDescriptor(
        "analyze", "command.analyze.title", "command.analyze.help", "analyze", ("task", "route")
    ),
    CommandDescriptor(
        "recommended_model",
        "command.recommended_model.title",
        "command.recommended_model.help",
        "recommended_model",
        ("model", "route"),
    ),
    CommandDescriptor(
        "dry_run", "command.dry_run.title", "command.dry_run.help", "dry_run", ("plan", "preview")
    ),
    CommandDescriptor(
        "open_plan",
        "command.open_plan.title",
        "command.open_plan.help",
        "open_plan",
        ("execute", "plan"),
    ),
    CommandDescriptor(
        id="refresh",
        title_message_id="command.refresh.title",
        help_message_id="command.refresh.help",
        action_id="refresh",
        keywords=("refresh", "quota", "provider", "reload"),
    ),
    CommandDescriptor(
        "run_doctor",
        "command.run_doctor.title",
        "command.run_doctor.help",
        "run_doctor",
        ("doctor", "diagnose", "rerun"),
    ),
    CommandDescriptor(
        "details",
        "command.details.title",
        "command.details.help",
        "details",
        ("details", "technical"),
    ),
    CommandDescriptor(
        "language",
        "command.language.title",
        "command.language.help",
        "setting:appearance.language",
        ("language", "locale", "日本語"),
    ),
    CommandDescriptor(
        "theme",
        "command.theme.title",
        "command.theme.help",
        "setting:appearance.tui_theme",
        ("theme", "dark", "light"),
    ),
    CommandDescriptor(
        "reserve",
        "command.reserve.title",
        "command.reserve.help",
        "setting:budget.reserve_fraction",
        ("reserve", "budget"),
    ),
    CommandDescriptor(
        id="help",
        title_message_id="command.help.title",
        help_message_id="command.help.help",
        action_id="help",
        keywords=("help", "keys", "shortcuts"),
    ),
    CommandDescriptor(
        id="quit",
        title_message_id="command.quit.title",
        help_message_id="command.quit.help",
        action_id="quit",
        keywords=("quit", "exit", "close"),
    ),
)


class _CommandHost(Protocol):
    localizer: Localizer

    def command_available(self, command_id: str) -> bool: ...

    def run_command(self, action_id: str) -> None: ...


class QuotaPilotCommandProvider(Provider):
    """Perform no I/O while discovering or searching commands."""

    def _host(self) -> _CommandHost:
        return cast(_CommandHost, self.app)

    def _available(self) -> tuple[CommandDescriptor, ...]:
        host = self._host()
        return tuple(command for command in COMMANDS if host.command_available(command.id))

    async def discover(self) -> Hits:
        host = self._host()
        for descriptor in self._available():
            yield DiscoveryHit(
                host.localizer.text(descriptor.title_message_id),
                lambda action=descriptor.action_id: host.run_command(action),
                help=host.localizer.text(descriptor.help_message_id),
            )

    async def search(self, query: str) -> Hits:
        host = self._host()
        matcher = self.matcher(query)
        for descriptor in self._available():
            title = host.localizer.text(descriptor.title_message_id)
            help_text = host.localizer.text(descriptor.help_message_id)
            searchable = " ".join((title, help_text, *descriptor.keywords))
            score = matcher.match(searchable)
            if score > 0:
                display = matcher.highlight(title) if matcher.match(title) > 0 else title
                yield Hit(
                    score,
                    display,
                    lambda action=descriptor.action_id: host.run_command(action),
                    help=help_text,
                )


def destination_for_command(command_id: str) -> Destination | None:
    try:
        return Destination(command_id)
    except ValueError:
        return None
