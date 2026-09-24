"""Qt-native language resolution and runtime translator management."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QCoreApplication, QLocale, QObject, QTranslator, Signal
from PySide6.QtQml import QQmlApplicationEngine

from quotapilot.config import LanguagePreference
from quotapilot.localization import resolve_language


def translation_directory() -> Path:
    return Path(__file__).resolve().parent / "i18n"


class TranslationManager(QObject):
    """Own the active QTranslator and retranslate one live QML engine."""

    languageChanged = Signal()

    def __init__(self, preference: LanguagePreference, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._preference = preference
        self._language = resolve_language(preference, QLocale.system().name())
        self._translator: QTranslator | None = None
        self._engine: QQmlApplicationEngine | None = None

    @Property(str, notify=languageChanged)
    def currentLanguage(self) -> str:  # noqa: N802 - QML property
        return self._language

    @Property(str, notify=languageChanged)
    def preference(self) -> str:
        return self._preference.value

    def attach_engine(self, engine: QQmlApplicationEngine) -> None:
        self._engine = engine

    def install_initial(self) -> None:
        self._install(self._language, retranslate=False)

    def set_preference(self, preference: LanguagePreference | str) -> bool:
        try:
            parsed = LanguagePreference(preference)
        except ValueError:
            return False
        resolved = resolve_language(parsed, QLocale.system().name())
        changed = parsed is not self._preference or resolved != self._language
        self._preference = parsed
        if changed:
            self._install(resolved, retranslate=True)
            self.languageChanged.emit()
        return changed

    def _install(self, language: str, *, retranslate: bool) -> None:
        application = QCoreApplication.instance()
        if application is None:
            raise RuntimeError("QCoreApplication must exist before installing translations")
        if self._translator is not None:
            application.removeTranslator(self._translator)
            self._translator = None
        if language != "en":
            translator = QTranslator(self)
            resource = translation_directory() / f"quotapilot_{language}.qm"
            if not translator.load(str(resource)):
                language = "en"
            else:
                application.installTranslator(translator)
                self._translator = translator
        self._language = language
        if retranslate and self._engine is not None:
            self._engine.retranslate()
