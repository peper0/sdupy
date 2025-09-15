import asyncio
import io
import traceback
from typing import Any, Callable, List, NamedTuple
import gc

import numpy as np
from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QTableView, QVBoxLayout, QWidget

from sdupy.pyreactive import unwrap_exception
from sdupy.pyreactive.notifier import Notifier, ScopedName
from sdupy.utils import ignore_errors
from sdupy.widgets.helpers import trigger_if_visible
from .common.register import register_widget
from ..pyreactive import Wrapped, reactive, unwrap


@register_widget("generic table")
class Table(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self._table_view = QTableView(self)
        self._table_view.horizontalHeader().setSectionsMovable(True)
        self.layout.addWidget(self._table_view)
        self.visibilityChanged = parent.visibilityChanged  # FIXME:

    def dump_state(self):
        return dict(
            header_state=bytes(self._table_view.horizontalHeader().saveState()).hex(),
        )

    def load_state(self, state: dict):
        if 'header_state' in state:
            self._table_view.horizontalHeader().restoreState(bytes.fromhex(state['header_state']))


@register_widget("variables table")
class VarsTable(Table):
    def __init__(self, parent, name):
        super().__init__(parent)
        self.model = VarsModel(self)
        self._table_view.setModel(self.model)

        self.insert_var = self.model.insert_var
        self.remove_var = self.model.remove_var
        self.clear = self.model.clear


class VarsModel(QAbstractTableModel):
    class VarInList(NamedTuple):
        name: str
        var: Wrapped
        notifier: Notifier
        to_value: Callable[[str], Any]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.vars = []  # type: List[VarsModel.VarInList]

    @ignore_errors
    def rowCount(self, parent=None):
        return len(self.vars)

    def columnCount(self, parent=None):
        return 2

    @ignore_errors
    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if index.isValid():
            if index.row() < len(self.vars):
                item = self.vars[index.row()]
                if role == Qt.DisplayRole or role == Qt.EditRole or role == Qt.ToolTipRole:
                    if index.column() == 0:
                        return item.name
                    elif index.column() == 1:
                        try:
                            return str(unwrap(item.var))
                        except Exception as e:
                            lines = []
                            while e:
                                lines.append('{{{}}} {}'.format(e.__class__.__name__, e))
                                e = e.__cause__
                            return '\n'.join(lines)
                if role == Qt.BackgroundColorRole:
                    if index.column() == 1:
                        exception = unwrap_exception(item.var)
                        if exception is not None:
                            return QColor('red')

    @ignore_errors
    def flags(self, index: QModelIndex):
        if index.row() < len(self.vars):
            item = self.vars[index.row()]
            return super().flags(index) | (Qt.ItemIsEditable if hasattr(item.var, 'set') else 0)
        return super().flags(index)

    @ignore_errors
    def setData(self, index: QModelIndex, value: Any, role: int):
        if index.isValid():
            if index.row() < len(self.vars):
                item = self.vars[index.row()]
                try:
                    converted_value = item.to_value(value)
                    item.var.set(converted_value)
                except Exception as e:
                    logging.exception('exception during setting var')
                    item.var.set_exception(e)
                return True
        return super().setData(index, value, role)

    def remove_var(self, name):
        indices_for_removal = [i for i, var_in_the_list in enumerate(self.vars) if var_in_the_list.name == name]

        for i in reversed(indices_for_removal):
            self.beginRemoveRows(QModelIndex(), i, i)
            del self.vars[i]
            self.endRemoveRows()

    def clear(self):
        if len(self.vars) > 0:
            self.beginRemoveRows(QModelIndex(), 0, len(self.vars) - 1)
            self.vars.clear()
            self.endRemoveRows()

    def insert_var(self, name: str, var: Wrapped, to_value: Callable[[str], Any]):
        assert var is not None
        self.remove_var(name)

        def notify_changed():
            for i, var_in_the_list in enumerate(self.vars):
                if var_in_the_list.var is var:
                    self.dataChanged.emit(self.index(i, 1), self.index(i, 1))
            return True

        with ScopedName('var {} in table'.format(name)):
            notifier = Notifier(notify_changed)
        var.__notifier__.add_observer(notifier)

        self.beginInsertRows(QModelIndex(), len(self.vars), len(self.vars))
        self.vars.append(VarsModel.VarInList(name=name, var=var, notifier=notifier, to_value=to_value))
        self.endInsertRows()

    @ignore_errors
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return "name" if section == 0 else "value"
            # if orientation == Qt.Vertical and role == Qt.DisplayRole:
            #    return self.data.index[section]


@register_widget("array table")
class ArrayTable(QWidget):
    DEFAULT_FORMAT = '{}'  # '{:.3g}' is good for floats, but there can be a nonfloat

    def __init__(self, parent, name):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self._table_view = QTableView(self)
        self.layout.addWidget(self._table_view)

        self._format = self.DEFAULT_FORMAT
        self._model = None
        self._var = None
        self._setter = None
        self._set_current_val(np.array([[]]))
        self.visibilityChanged = parent.visibilityChanged  # FIXME:
        self.update()

    @property
    def var(self):
        return self._var

    @var.setter
    def var(self, new_var):
        self._var = new_var
        self._setter = None
        gc.collect()
        self.update()

    @property
    def format(self):
        return self._format

    @format.setter
    def format(self, format_):
        self._format = format_ or self.DEFAULT_FORMAT
        self.update()

    def update(self):
        self._setter = trigger_if_visible(reactive(self._set_current_val)(self._var), self)

    def _set_current_val(self, val):
        self._model = ArrayModel(val, self)
        self._model.format = self._format
        self._table_view.setModel(self._model)


class ArrayModel(QAbstractTableModel):
    def __init__(self, array: np.ndarray, parent=None):
        super().__init__(parent)
        if array is None:
            array = np.eye(0)
        assert hasattr(array, 'shape'), "expected array, got {} of type {}".format(array, type(array))
        assert hasattr(array, '__getitem__')
        self._array = array  # type: np.ndarray
        self.format = None
        if self._array.ndim >= 2:
            self._columns = list(range(self._array.shape[1]))
        else:
            self._columns = self._array.dtype.names

        # if array.shape[0]>0:
        #     self.beginInsertRows(QModelIndex(), 0, array.shape[0]-1)
        #     self.endInsertRows()
        #
        # if array.shape[1]>0:
        #     self.beginInsertColumns(QModelIndex(), 0, array.shape[1]-1)
        #     self.endInsertColumns()
        #
        #     self.dataChanged.emit(self.index(0, 0), self.index(array.shape[0]-1, array.shape[1]-1))

    @ignore_errors(retval=0)
    def rowCount(self, parent=None):
        return self._array.shape[0]

    @ignore_errors(retval=0)
    def columnCount(self, parent=None):
        return len(self._columns)

    @ignore_errors
    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        assert self.format is not None
        assert isinstance(self.format, str)
        if self._index_is_good(index):
            if role in [Qt.DisplayRole, Qt.EditRole, Qt.ToolTipRole, Qt.StatusTipRole]:
                res = self.format.format(self._array[index.row()][index.column()])
                return res

    @ignore_errors(retval=Qt.ItemFlags())
    def flags(self, index: QModelIndex):
        if self._index_is_good(index):
            return super().flags(index) | (Qt.ItemIsEditable if True else 0)
        return super().flags(index)

    def _index_is_good(self, index: QModelIndex):
        res = (index.isValid()
               and index.row() < self._array.shape[0]
               and index.column() < len(self._columns))
        return res

    @ignore_errors
    def setData(self, index: QModelIndex, value: Any, role: int):
        if self._index_is_good(index):
            try:
                self._array[index.row()][index.column()] = eval(value)
            except Exception as e:
                logging.exception('exception during setting var (ignoring)')
            return True
        return super().setData(index, value, role)

    @ignore_errors
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._columns[section])
            else:
                return str(section)


@reactive()
async def gen(n, t=1):
    for i in range(n):
        await asyncio.sleep(t)
        yield 1 + i * i


import logging
import logging.handlers


class LogRecordsModel(QAbstractTableModel, logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []  # type: List[logging.LogRecord]
        self.columns = ['timestamp', 'name', 'level', 'message', 'path', 'file']
        self.records_limit = 100000
        self.bg_colors = {
            logging.CRITICAL: QColor(Qt.magenta).lighter(),
            logging.ERROR: QColor(Qt.red).lighter(),
            logging.WARNING: QColor(Qt.yellow).lighter(),
            logging.INFO: QColor(Qt.green).lighter(),
            logging.DEBUG: QColor(Qt.cyan).lighter(),
        }

    def emit(self, record: logging.LogRecord):
        if len(self.records) > self.records_limit:
            chunk_size = 10
            self.beginRemoveRows(QModelIndex(), 0, chunk_size - 1)
            del self.records[0:chunk_size]  # it's probably faster to remove in greater chunks
            self.endRemoveRows()

        try:
            self.beginInsertRows(QModelIndex(), len(self.records), len(self.records))
            self.records.append(record)
            self.endInsertRows()
        except Exception:
            self.handleError(record)

    def __repr__(self):
        level = logging.getLevelName(self.level)
        return '<%s (%s)>' % (self.__class__.__name__, level)

    def rowCount(self, parent=None):
        return len(self.records)

    def columnCount(self, parent=None):
        return len(self.columns)

    def data(self, index, role=Qt.DisplayRole):
        if index.isValid():
            if index.row() < len(self.records) and index.column() < len(self.columns):
                record = self.records[index.row()]
                col_name = self.columns[index.column()]
                if role == Qt.DisplayRole or role == Qt.ToolTipRole:
                    if col_name == 'message':
                        if record.exc_info:
                            if role == Qt.ToolTipRole:
                                return record.getMessage() + '\n' + self.formatException(record.exc_info)
                            else:
                                return record.getMessage() + " (see tooltop for more)"
                        else:
                            return record.getMessage()
                    elif col_name == 'level':
                        return record.levelname
                    elif col_name == 'timestamp':
                        return '{:.3f}'.format(record.relativeCreated)
                    elif col_name == 'path':
                        return record.pathname
                    elif col_name == 'file':
                        return record.filename + ":" + str(record.lineno)
                    elif col_name == 'name':
                        return record.name
                elif role == Qt.BackgroundColorRole:
                    # TODO interpolate between two nearest?
                    if record.levelno in self.bg_colors:
                        return self.bg_colors[record.levelno]

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.columns[section]

    def formatException(self, ei):
        """
        Stolen from logging module.

        Format and return the specified exception information as a string.

        This default implementation just uses
        traceback.print_exception()
        """
        sio = io.StringIO()
        tb = ei[2]
        # See issues #9427, #1553375. Commented out for now.
        # if getattr(self, 'fullstack', False):
        #    traceback.print_stack(tb.tb_frame.f_back, file=sio)
        traceback.print_exception(ei[0], ei[1], tb, None, sio)
        s = sio.getvalue()
        sio.close()
        if s[-1:] == "\n":
            s = s[:-1]
        return s


# global_logger_handler = LogRecordsModel()

# logging.getLogger().setLevel(logging.DEBUG)
# global_logger_handler.setLevel(logging.DEBUG)

# logging.getLogger().setLevel(logging.INFO)
# global_logger_handler.setLevel(logging.INFO)


@register_widget("logs")
class Logs(Table):
    def __init__(self, parent, name):
        global_logger_handler = LogRecordsModel()
        logging.getLogger().addHandler(global_logger_handler)
        super().__init__(parent)
        self._table_view.setModel(global_logger_handler)
