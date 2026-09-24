"""Framework-neutral locale resolution shared by presentation layers."""

from __future__ import annotations

from quotapilot.config.models import LanguagePreference

SUPPORTED_LANGUAGES = ("en", "ja")


def resolve_language(preference: LanguagePreference | str, system_locale: str) -> str:
    """Resolve explicit preference, then supplied system locale, then English."""
    try:
        configured = LanguagePreference(preference)
    except ValueError:
        return "en"
    if configured is not LanguagePreference.SYSTEM:
        return configured.value
    normalized = system_locale.strip().replace("-", "_").lower()
    return "ja" if normalized == "ja" or normalized.startswith("ja_") else "en"
