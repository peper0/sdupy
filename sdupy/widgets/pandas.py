import logging

import numpy as np
import pandas as pd
from PyQt5.QtCore import QAbstractTableModel, Qt
from PyQt5.QtWidgets import QLineEdit

from sdupy import reactive
from sdupy.widgets import register_widget
from sdupy.widgets.tables import Table


@register_widget("data_table")
class PandasTable(Table):
    def __init__(self, parent):
        super().__init__(parent)
        self.model = DataTreeModel(self)
        self._table_view.setModel(self.model)
        # self._table_view.setSortingEnabled(True)

        self._filter_edit = QLineEdit(self)
        self._filter_edit.editingFinished.connect(lambda: self.model.set_query(self._filter_edit.text()))
        self.layout.insertWidget(0, self._filter_edit)

    @reactive()
    def set_data(self, data: pd.DataFrame):
        if data is None:
            data = pd.DataFrame()
        self.model.set_data(data)


class DataTreeModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        size = 1000 * 100
        arr = ((int(n) for n in d) for d in np.array(np.random.randn(size, 4)))
        # arrs=np.array(list(map(tuple, arr.tolist())), dtype=dict(names=['a', 'b', 'c', 'd'], formats=[np.float]*4))
        test_data = pd.DataFrame(arr, columns=['a', 'b', 'c', 'd'])
        self.original_data = test_data
        self.data = self.original_data
        self.query_is_ok = True

        self._sort_columns = []
        self._query = None

    def rowCount(self, parent=None):
        return len(self.data)

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

    def rebuild_data(self):
        self.beginResetModel()
        self.data = self.original_data
        self.query_is_ok = True
        try:
            if self._sort_columns:
                cols, orders = zip(*reversed(self._sort_columns))
                self.data = self.data.sort_values(by=list(cols), ascending=list(orders))
            self.query_is_ok = False
            if self._query:
                self.data = self.data.query(self._query)
                self.query_is_ok = True
        except Exception:
            logging.exception("ignoring")
        self.endResetModel()

    def sort(self, column: int, order: Qt.SortOrder):
        column_name = self.original_data.columns[column]
        self._sort_columns = list(filter(lambda t: t[0] != column_name, self._sort_columns))
        self._sort_columns.append((column_name, order == Qt.AscendingOrder))
        while len(self._sort_columns) > 5:
            self._sort_columns.pop(0)
        self.rebuild_data()

    def set_query(self, query: str):
        self._query = query
        self.rebuild_data()

    def set_data(self, data):
        self.original_data = data
        self.rebuild_data()


@reactive()
async def append_data_frame(gen):
    res = pd.DataFrame(index=[], columns=['a'])
    async for v in gen:
        res.loc[len(res.index), 'a'] = v
        yield res