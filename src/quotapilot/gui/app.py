"""PySide6/QML application bootstrap."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from quotapilot.config import load_effective_config

from .controllers.app_controller import AppController
from .dependencies import build_dependencies
from .localization import TranslationManager


def qml_directory() -> Path:
    return Path(__file__).resolve().parent / "qml"


def run_gui(
    *,
    smoke_test: bool = False,
    smoke_size: tuple[int, int] | None = None,
) -> int:
    """Launch the desktop GUI, optionally quitting after an offscreen load."""
    if smoke_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QSG_RHI_BACKEND", "software")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")

    application = QGuiApplication.instance() or QGuiApplication(sys.argv)
    application.setApplicationName("QuotaPilot")
    application.setOrganizationName("QuotaPilot")

    effective = load_effective_config()
    engine = QQmlApplicationEngine()
    translations = TranslationManager(effective.config.appearance.language, engine)
    translations.attach_engine(engine)
    translations.install_initial()
    controller = AppController(
        build_dependencies(effective),
        translations,
        smoke_mode=smoke_test,
    )
    # Tie context-object lifetime to the engine so QML bindings are dismantled
    # before their Python owners disappear during smoke-test shutdown.
    controller.setParent(engine)
    context = engine.rootContext()
    context.setContextProperty("appController", controller)
    context.setContextProperty("overviewViewModel", controller.overview)
    context.setContextProperty("usageViewModel", controller.usage)
    context.setContextProperty("modelsViewModel", controller.models)
    context.setContextProperty("routeViewModel", controller.route)
    context.setContextProperty("executeViewModel", controller.execute)
    context.setContextProperty("historyViewModel", controller.history)
    context.setContextProperty("settingsViewModel", controller.settings)
    context.setContextProperty("commandPalette", controller.palette)
    engine.addImportPath(str(qml_directory()))
    engine.load(QUrl.fromLocalFile(str(qml_directory() / "Main.qml")))
    if not engine.rootObjects():
        return 1
    if smoke_size is not None:
        root = engine.rootObjects()[0]
        root.setProperty("width", smoke_size[0])
        root.setProperty("height", smoke_size[1])
    if smoke_test:
        # Loading every component is the packaging/QML smoke gate. Avoid entering
        # a platform render loop in headless CI, where Qt's offscreen backend can
        # differ materially from the supported Wayland/X11 desktop target.
        # Destroy QML roots while context objects are still alive; otherwise Qt
        # reevaluates bindings against null context properties during teardown.
        for root in engine.rootObjects():
            root.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        return 0
    return application.exec()


def main() -> None:
    raise SystemExit(run_gui())
