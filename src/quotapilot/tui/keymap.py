"""Single binding registry for app bindings, footer hints, and Help."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from textual.binding import Binding, BindingType

from quotapilot.tui.state import DESTINATIONS, Destination


class InputContext(StrEnum):
    NAVIGATION = "navigation"
    TEXT_INPUT = "text_input"
    MODAL = "modal"


class HelpGroup(StrEnum):
    NAVIGATION = "navigation"
    ACTIONS = "actions"
    GLOBAL = "global"


@dataclass(frozen=True, slots=True)
class KeySpec:
    keys: str
    key_display: str
    action: str
    description_id: str
    help_group: HelpGroup
    contexts: frozenset[InputContext]
    destinations: frozenset[Destination] = frozenset()
    footer_id: str | None = None
    footer_group: str | None = None
    priority: bool = False

    def applies(self, destination: Destination, context: InputContext) -> bool:
        return context in self.contexts and (
            not self.destinations or destination in self.destinations
        )


_NAVIGATION = frozenset({InputContext.NAVIGATION})
_ALL_DESTINATIONS = frozenset(DESTINATIONS)

KEY_SPECS: tuple[KeySpec, ...] = (
    KeySpec(
        "j,down",
        "j / Down",
        "navigate_down",
        "help.next",
        HelpGroup.NAVIGATION,
        _NAVIGATION,
        footer_id="footer.move",
        footer_group="move",
    ),
    KeySpec(
        "k,up",
        "k / Up",
        "navigate_up",
        "help.previous",
        HelpGroup.NAVIGATION,
        _NAVIGATION,
        footer_id="footer.move",
        footer_group="move",
    ),
    KeySpec(
        "enter",
        "Enter",
        "activate",
        "help.activate",
        HelpGroup.NAVIGATION,
        _NAVIGATION,
        _ALL_DESTINATIONS,
        footer_id="footer.open",
        footer_group="activate",
    ),
    KeySpec(
        "h,left",
        "h / Left",
        "navigate_left",
        "help.back",
        HelpGroup.NAVIGATION,
        _NAVIGATION,
        footer_id="footer.back",
        footer_group="back",
    ),
    KeySpec(
        "l,right",
        "l / Right",
        "navigate_right",
        "help.activate",
        HelpGroup.NAVIGATION,
        _NAVIGATION,
    ),
    KeySpec(
        "escape",
        "Esc",
        "go_back",
        "help.back",
        HelpGroup.NAVIGATION,
        frozenset({InputContext.NAVIGATION, InputContext.TEXT_INPUT}),
        footer_id="footer.back",
        footer_group="safe-back",
    ),
    KeySpec(
        "r",
        "r",
        "refresh",
        "help.refresh",
        HelpGroup.ACTIONS,
        _NAVIGATION,
        frozenset(
            {
                Destination.OVERVIEW,
                Destination.MODELS,
                Destination.USAGE,
                Destination.HISTORY,
                Destination.DOCTOR,
            }
        ),
        footer_id="footer.refresh",
        footer_group="refresh",
    ),
    KeySpec(
        "ctrl+enter",
        "Ctrl+Enter",
        "analyze_task",
        "help.analyze",
        HelpGroup.ACTIONS,
        frozenset({InputContext.NAVIGATION, InputContext.TEXT_INPUT}),
        frozenset({Destination.ROUTE}),
        footer_id="footer.analyze",
        priority=True,
    ),
    KeySpec(
        "ctrl+d",
        "Ctrl+D",
        "toggle_details",
        "help.details",
        HelpGroup.ACTIONS,
        _NAVIGATION,
        frozenset({Destination.ROUTE, Destination.MODELS, Destination.USAGE}),
        footer_id="footer.details",
    ),
    KeySpec(
        "slash",
        "/",
        "filter_local",
        "help.filter",
        HelpGroup.ACTIONS,
        _NAVIGATION,
        frozenset({Destination.MODELS, Destination.HISTORY, Destination.SETTINGS}),
        footer_id="footer.filter",
    ),
    KeySpec(
        "ctrl+p",
        "Ctrl+P",
        "command_palette",
        "help.commands",
        HelpGroup.GLOBAL,
        frozenset({InputContext.NAVIGATION, InputContext.TEXT_INPUT}),
        footer_id="footer.commands",
        footer_group="commands",
        priority=True,
    ),
    KeySpec(
        "question_mark",
        "?",
        "context_help",
        "help.help",
        HelpGroup.GLOBAL,
        _NAVIGATION,
        footer_id="footer.help",
        footer_group="help",
    ),
    KeySpec(
        "q",
        "q",
        "request_quit",
        "help.quit",
        HelpGroup.GLOBAL,
        _NAVIGATION,
        footer_id="footer.quit",
        footer_group="quit",
    ),
)


def app_bindings() -> list[BindingType]:
    seen: set[tuple[str, str]] = set()
    bindings: list[BindingType] = []
    for spec in KEY_SPECS:
        identity = (spec.keys, spec.action)
        if identity in seen:
            continue
        seen.add(identity)
        bindings.append(
            Binding(
                spec.keys,
                spec.action,
                show=False,
                key_display=spec.key_display,
                priority=spec.priority,
                id=spec.action,
            )
        )
    return bindings


def help_specs(destination: Destination) -> tuple[KeySpec, ...]:
    return tuple(spec for spec in KEY_SPECS if spec.applies(destination, InputContext.NAVIGATION))


def footer_specs(
    destination: Destination,
    *,
    navigation_focused: bool,
    compact: bool,
) -> tuple[KeySpec, ...]:
    by_action = {spec.action: spec for spec in help_specs(destination)}
    actions: tuple[str, ...]
    if navigation_focused:
        actions = (
            "navigate_down",
            "activate",
            "go_back" if destination is not Destination.OVERVIEW else "request_quit",
            "command_palette",
            "context_help",
        )
    elif destination is Destination.OVERVIEW:
        actions = (
            "navigate_left" if compact else "activate",
            "refresh",
            "command_palette",
            "context_help",
            "request_quit",
        )
    elif destination is Destination.ROUTE:
        actions = (
            "analyze_task",
            "toggle_details",
            "go_back",
            "context_help",
        )
    elif destination is Destination.MODELS:
        actions = (
            "navigate_down",
            "activate",
            "filter_local",
            "refresh",
            "context_help",
        )
    elif destination is Destination.EXECUTE:
        actions = ("activate", "go_back", "context_help")
    elif destination is Destination.USAGE:
        actions = ("refresh", "toggle_details", "go_back", "context_help")
    elif destination is Destination.HISTORY:
        actions = ("navigate_down", "activate", "filter_local", "go_back", "context_help")
    elif destination is Destination.SETTINGS:
        actions = ("navigate_down", "activate", "filter_local", "go_back", "context_help")
    elif destination is Destination.DOCTOR:
        actions = ("navigate_down", "activate", "refresh", "go_back", "context_help")
    else:
        actions = (
            "go_back",
            "navigate_left" if compact else "command_palette",
            "command_palette",
            "context_help",
            "request_quit",
        )
    return tuple(by_action[action] for action in actions if action in by_action)
