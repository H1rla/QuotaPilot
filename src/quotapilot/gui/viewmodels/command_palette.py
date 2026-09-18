"""Keyboard-first command palette state."""

from __future__ import annotations

from PySide6.QtCore import Property, QCoreApplication, QObject, Signal, Slot

from ..commands import PaletteCommand, filter_commands
from ..list_model import DictListModel


class CommandPaletteViewModel(QObject):
    stateChanged = Signal()
    commandActivated = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._open = False
        self._query = ""
        self._selected_index = 0
        self.model = DictListModel(("commandId", "title", "hint"))
        self._commands: tuple[PaletteCommand, ...] = ()
        self._refilter()

    @Property(QObject, constant=True)
    def rows(self) -> QObject:
        return self.model

    @Property(bool, notify=stateChanged)
    def open(self) -> bool:
        return self._open

    @Property(str, notify=stateChanged)
    def query(self) -> str:
        return self._query

    @Property(int, notify=stateChanged)
    def selectedIndex(self) -> int:  # noqa: N802
        return self._selected_index

    @Slot()
    def show(self) -> None:
        self._open = True
        self._query = ""
        self._selected_index = 0
        self._refilter()
        self.stateChanged.emit()

    @Slot()
    def close(self) -> None:
        self._open = False
        self.stateChanged.emit()

    @Slot(str)
    def setQuery(self, query: str) -> None:  # noqa: N802
        self._query = query
        self._selected_index = 0
        self._refilter()
        self.stateChanged.emit()

    @Slot(int)
    def setSelectedIndex(self, index: int) -> None:  # noqa: N802
        if self._commands:
            self._selected_index = max(0, min(index, len(self._commands) - 1))
            self.stateChanged.emit()

    @Slot()
    def moveNext(self) -> None:  # noqa: N802
        self.setSelectedIndex(self._selected_index + 1)

    @Slot()
    def movePrevious(self) -> None:  # noqa: N802
        self.setSelectedIndex(self._selected_index - 1)

    @Slot()
    def activateSelected(self) -> None:  # noqa: N802
        if not self._commands:
            return
        command = self._commands[self._selected_index]
        self._open = False
        self.stateChanged.emit()
        self.commandActivated.emit(command.id)

    @Slot(int)
    def activate(self, index: int) -> None:
        self.setSelectedIndex(index)
        self.activateSelected()

    def _refilter(self) -> None:
        def translate(text: str) -> str:
            return QCoreApplication.translate("Global", text)

        self._commands = filter_commands(self._query, translate)
        self.model.replace(
            {
                "commandId": command.id,
                "title": translate(command.title),
                "hint": translate(command.hint),
            }
            for command in self._commands
        )

    @Slot()
    def retranslate(self) -> None:
        self._refilter()
        self.stateChanged.emit()
