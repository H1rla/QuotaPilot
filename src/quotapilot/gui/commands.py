"""Pure command-palette registry and deterministic fuzzy filtering."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PaletteCommand:
    id: str
    title: str
    hint: str
    keywords: tuple[str, ...] = ()


COMMANDS: tuple[PaletteCommand, ...] = (
    PaletteCommand("overview", "Open Overview", "Overview", ("home", "quota")),
    PaletteCommand("usage", "Open Usage", "Usage", ("history", "pace")),
    PaletteCommand("models", "Open Models", "Models", ("profiles", "capability")),
    PaletteCommand("route", "Route a task", "Route", ("analyze", "recommend")),
    PaletteCommand("execute", "Open Execution", "Execute", ("plan", "approval")),
    PaletteCommand("history", "Open History", "History", ("snapshots",)),
    PaletteCommand("settings", "Open Settings", "Settings", ("configuration",)),
    PaletteCommand("settings-budget", "Change budget reserve", "Settings · Budget", ("reserve",)),
    PaletteCommand(
        "settings-routing",
        "Change routing policy",
        "Settings · Routing",
        ("pressure",),
    ),
    PaletteCommand("refresh", "Refresh quota", "Ctrl+R", ("provider", "capture")),
    PaletteCommand("details", "Toggle details", "Ctrl+D", ("technical", "provenance")),
)


def filter_commands(query: str) -> tuple[PaletteCommand, ...]:
    normalized = " ".join(query.lower().split())
    if not normalized:
        return COMMANDS

    def score(command: PaletteCommand) -> tuple[int, int, str] | None:
        haystack = " ".join((command.title, command.hint, *command.keywords)).lower()
        direct = haystack.find(normalized)
        if direct >= 0:
            return (0, direct, command.title)
        position = -1
        gap = 0
        for character in normalized:
            next_position = haystack.find(character, position + 1)
            if next_position < 0:
                return None
            if position >= 0:
                gap += next_position - position - 1
            position = next_position
        return (1, gap, command.title)

    ranked = [(match, command) for command in COMMANDS if (match := score(command))]
    ranked.sort(key=lambda item: item[0])
    return tuple(command for _score, command in ranked)
