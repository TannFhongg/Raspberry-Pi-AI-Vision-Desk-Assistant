"""Generic list models used by repeating Qt Quick UI collections."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt


class DictListModel(QAbstractListModel):
    """Minimal `QAbstractListModel` backed by a list of dictionaries."""

    def __init__(self, roles: list[str], parent=None) -> None:
        super().__init__(parent)
        self._roles = list(roles)
        self._items: list[dict[str, Any]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        row = index.row()
        if row < 0 or row >= len(self._items):
            return None
        role_name = self._role_name(role)
        if role_name is None:
            return None
        return self._items[row].get(role_name)

    def roleNames(self) -> dict[int, bytes]:
        return {
            Qt.UserRole + offset + 1: role.encode("utf-8")
            for offset, role in enumerate(self._roles)
        }

    def items(self) -> list[dict[str, Any]]:
        """Return a copy of the stored list payload."""
        return [item.copy() for item in self._items]

    def set_items(self, items: list[dict[str, Any]]) -> None:
        """Replace the current item list."""
        self.beginResetModel()
        self._items = [item.copy() for item in items]
        self.endResetModel()

    def clear(self) -> None:
        """Remove all list items."""
        self.set_items([])

    def _role_name(self, role: int) -> str | None:
        offset = role - Qt.UserRole - 1
        if 0 <= offset < len(self._roles):
            return self._roles[offset]
        return None

