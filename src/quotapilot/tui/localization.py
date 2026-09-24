"""Packaged YAML localization with an English runtime fallback."""

from __future__ import annotations

import locale
from pathlib import Path
from typing import Any

import yaml
from rich.cells import cell_len, set_cell_size

from quotapilot.config import LanguagePreference
from quotapilot.localization import resolve_language


class CatalogError(ValueError):
    """A packaged translation catalog is malformed."""


def catalog_directory() -> Path:
    return Path(__file__).resolve().parent / "locales"


def load_catalog(language: str, *, directory: Path | None = None) -> dict[str, str]:
    path = (directory or catalog_directory()) / f"{language}.yaml"
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CatalogError(f"unable to load TUI catalog {language!r}") from exc
    if not isinstance(raw, dict) or any(
        not isinstance(key, str) or not isinstance(value, str) for key, value in raw.items()
    ):
        raise CatalogError(f"TUI catalog {language!r} must map strings to strings")
    return dict(raw)


def validate_catalogs(*, directory: Path | None = None) -> None:
    english = load_catalog("en", directory=directory)
    japanese = load_catalog("ja", directory=directory)
    if english.keys() != japanese.keys():
        missing_ja = sorted(english.keys() - japanese.keys())
        missing_en = sorted(japanese.keys() - english.keys())
        raise CatalogError(
            f"TUI catalogs have different keys; missing ja={missing_ja}, missing en={missing_en}"
        )


def system_locale_name() -> str:
    """Return a locale hint; pure resolution remains separately testable."""
    language, _encoding = locale.getlocale()
    return language or "en"


class Localizer:
    def __init__(self, language: str, *, directory: Path | None = None) -> None:
        self.language = language if language in {"en", "ja"} else "en"
        self._english = load_catalog("en", directory=directory)
        self._active = (
            self._english
            if self.language == "en"
            else load_catalog(self.language, directory=directory)
        )

    @classmethod
    def from_preference(
        cls,
        preference: LanguagePreference | str,
        *,
        system_locale: str | None = None,
        directory: Path | None = None,
    ) -> Localizer:
        language = resolve_language(preference, system_locale or system_locale_name())
        return cls(language, directory=directory)

    def text(self, message_id: str, **values: object) -> str:
        template = self._active.get(message_id, self._english.get(message_id, message_id))
        try:
            return template.format(**values)
        except (KeyError, ValueError):
            fallback = self._english.get(message_id, message_id)
            try:
                return fallback.format(**values)
            except (KeyError, ValueError):
                return fallback


def truncate_cells(value: str, maximum: int) -> str:
    """Elide by terminal cells, never by Python code-point count."""
    if maximum <= 0:
        return ""
    if cell_len(value) <= maximum:
        return value
    if maximum == 1:
        return "…"
    return set_cell_size(value, maximum - 1).rstrip() + "…"
