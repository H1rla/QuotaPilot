"""Shared observable operation state for GUI view models."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot


class BaseViewModel(QObject):
    stateChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._busy = False
        self._error_message = ""
        self._error_action = ""

    @Property(bool, notify=stateChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(str, notify=stateChanged)
    def errorMessage(self) -> str:  # noqa: N802 - QML property
        return self._error_message

    @Property(str, notify=stateChanged)
    def errorAction(self) -> str:  # noqa: N802 - QML property
        return self._error_action

    @Property(bool, notify=stateChanged)
    def hasError(self) -> bool:  # noqa: N802 - QML property
        return bool(self._error_message)

    def _begin(self) -> None:
        self._busy = True
        self._error_message = ""
        self._error_action = ""
        self.stateChanged.emit()

    def _finish(self) -> None:
        self._busy = False
        self.stateChanged.emit()

    def _fail(self, message: str, action: str = "Retry") -> None:
        self._busy = False
        self._error_message = message
        self._error_action = action
        self.stateChanged.emit()

    @Slot()
    def clearError(self) -> None:  # noqa: N802 - Qt slot
        self._error_message = ""
        self._error_action = ""
        self.stateChanged.emit()

