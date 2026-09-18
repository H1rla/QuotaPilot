"""Read-only dictionary list model used by compact QML tables and lists."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    Signal,
    Slot,
)

_INVALID_INDEX = QModelIndex()


class DictListModel(QAbstractListModel):
    countChanged = Signal()

    def __init__(self, roles: Sequence[str]) -> None:
        super().__init__()
        self._roles = tuple(roles)
        self._role_ids = {
            Qt.ItemDataRole.UserRole + index: role
            for index, role in enumerate(self._roles, start=1)
        }
        self._items: tuple[dict[str, Any], ...] = ()

    def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802 - Qt API
        return {role_id: QByteArray(role.encode()) for role_id, role in self._role_ids.items()}

    def rowCount(  # noqa: N802
        self,
        parent: QModelIndex | QPersistentModelIndex = _INVALID_INDEX,
    ) -> int:
        return 0 if parent.isValid() else len(self._items)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        key = self._role_ids.get(role)
        return None if key is None else self._items[index.row()].get(key)

    def replace(self, items: Iterable[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._items = tuple(dict(item) for item in items)
        self.endResetModel()
        self.countChanged.emit()

    @Slot(int, result="QVariant")
    def get(self, index: int) -> dict[str, Any]:
        if 0 <= index < len(self._items):
            return dict(self._items[index])
        return {}

    @property
    def items(self) -> tuple[dict[str, Any], ...]:
        return self._items
