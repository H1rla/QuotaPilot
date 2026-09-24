"""QuotaPilot Textual themes and deterministic System fallback."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import App
from textual.theme import Theme

from quotapilot.config import TuiThemePreference


@dataclass(frozen=True, slots=True)
class ThemeResolution:
    preference: TuiThemePreference
    resolved: TuiThemePreference
    textual_name: str
    used_fallback: bool


_DARK_COLORS = {
    "primary": "#4F6FD6",
    "secondary": "#A5B1C4",
    "warning": "#d6a657",
    "error": "#df6b72",
    "success": "#4fa873",
    "accent": "#4F6FD6",
    "foreground": "#E8EEF8",
    "background": "#08111B",
    "surface": "#0D1724",
    "panel": "#132033",
    "border": "#243247",
    "muted": "#707F96",
    "stale": "#b58b49",
    "accent-hover": "#6381DE",
    "accent-pressed": "#3F5FC5",
    "accent-subtle": "#15213A",
    "accent-focus": "#708DE3",
    "accent-on": "#F7F9FC",
}

_LIGHT_COLORS = {
    "primary": "#334E9E",
    "secondary": "#4D5B72",
    "warning": "#8a5b00",
    "error": "#a4252d",
    "success": "#176b43",
    "accent": "#334E9E",
    "foreground": "#172033",
    "background": "#F5F7FB",
    "surface": "#FFFFFF",
    "panel": "#EEF2F8",
    "border": "#D6DCE8",
    "muted": "#647188",
    "stale": "#76531a",
    "accent-hover": "#405EB4",
    "accent-pressed": "#2B4389",
    "accent-subtle": "#E8EDF9",
    "accent-focus": "#526EC2",
    "accent-on": "#FFFFFF",
}


def _theme(
    name: str,
    colors: dict[str, str],
    *,
    dark: bool,
) -> Theme:
    return Theme(
        name=name,
        dark=dark,
        primary=colors["primary"],
        secondary=colors["secondary"],
        warning=colors["warning"],
        error=colors["error"],
        success=colors["success"],
        accent=colors["accent"],
        foreground=colors["foreground"],
        background=colors["background"],
        surface=colors["surface"],
        panel=colors["panel"],
        variables={
            "muted": colors["muted"],
            "stale": colors["stale"],
            "accent-hover": colors["accent-hover"],
            "accent-pressed": colors["accent-pressed"],
            "accent-subtle": colors["accent-subtle"],
            "accent-focus": colors["accent-focus"],
            "accent-on": colors["accent-on"],
            "focus-foreground": colors["accent-on"],
            "border": colors["accent-focus"],
            "border-blurred": colors["border"],
            "text-muted": colors["muted"],
            "block-cursor-background": colors["accent-subtle"],
            "block-cursor-foreground": colors["foreground"],
            "block-cursor-blurred-background": colors["panel"],
            "block-cursor-blurred-foreground": colors["foreground"],
            "input-selection-background": colors["accent-subtle"],
            "input-selection-foreground": colors["foreground"],
            "link-background-hover": colors["accent-subtle"],
            "link-color": colors["accent-focus"],
            "link-color-hover": colors["accent-hover"],
            "footer-key-foreground": colors["muted"],
        },
    )


QUOTAPILOT_THEMES: tuple[Theme, ...] = (
    # Textual cannot reliably discover terminal background brightness. The
    # System entry is therefore an explicit Dark fallback, not a guessed ANSI
    # surface (ANSI themes require terminal variables Textual cannot infer).
    _theme("quotapilot-system", _DARK_COLORS, dark=True),
    _theme("quotapilot-dark", _DARK_COLORS, dark=True),
    _theme("quotapilot-light", _LIGHT_COLORS, dark=False),
)


def resolve_theme(preference: TuiThemePreference | str) -> ThemeResolution:
    try:
        parsed = TuiThemePreference(preference)
    except ValueError:
        parsed = TuiThemePreference.SYSTEM
    if parsed is TuiThemePreference.SYSTEM:
        return ThemeResolution(
            preference=parsed,
            resolved=TuiThemePreference.DARK,
            textual_name="quotapilot-system",
            used_fallback=True,
        )
    return ThemeResolution(
        preference=parsed,
        resolved=parsed,
        textual_name=f"quotapilot-{parsed.value}",
        used_fallback=False,
    )


def register_themes(app: App[object]) -> None:
    for theme in QUOTAPILOT_THEMES:
        app.register_theme(theme)
