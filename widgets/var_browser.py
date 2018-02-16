from typing import Any, NamedTuple

from PyQt5.QtCore import QAbstractItemModel, QModelIndex, Qt
from PyQt5.QtWidgets import QTreeView, QVBoxLayout, QWidget

from .common.register import register_widget


@register_widget("data_table")
class VarBrowser(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self._tree_view = QTreeView(self)
        self.model = VarsTreeModel(self)
        self._tree_view.setModel(self.model)
        # self._table_view.setSortingEnabled(True)

        self._tree_view.horizontalHeader().setSectionsMovable(True)

        # self._filter_edit = QLineEdit(self)
        # self._filter_edit.editingFinished.connect(lambda: self.model.set_query(self._filter_edit.text()))
        # self.layout.addWidget(self._filter_edit)
        self.layout.addWidget(self._tree_view)


class VarData(NamedTuple):
    name: str
    expr: str
    data: Any
    parent: VarData
    children: [VarData]


def _obtain_children(data: Any):
    if isinstance(data, dict):
        return [VarData(name=key, expr='{}[{}]'.format(data.expr)
                for key, value in data.items()]


class VarsTreeModel(QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = dict(a=5, b="hej")
        self.root_var_data = VarData(name='', expr='', data=self.data, parent=None, children=None)

    def _vd_for_index(self, index: QModelIndex):
        if index and index.isValid():
            return index.internalPointer()
        else:
            return self.root_var_data

    def rowCount(self, parent: QModelIndex = None):
        vd = self._vd_for_index(parent)

    def columnCount(self, parent=None):
        return len(self.data.columns)

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if role == Qt.DisplayRole:
                return str(self.data.iloc[index.row(), index.column()])

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.data.columns[section]
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return self.data.index[section]
