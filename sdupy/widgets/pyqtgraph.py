import asyncio
import os
import logging
import time
import weakref
from inspect import iscoroutinefunction
from typing import Callable, Optional

import pyqtgraph as pg
from PyQt5 import QtCore
from PyQt5.QtCore import Qt, QMimeData
from PyQt5.QtGui import QColor, QFont, QDragEnterEvent, QDropEvent
from PyQt5.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget, \
    QApplication, QTreeWidgetItem
from pyqtgraph import ItemSample
from pyqtgraph.parametertree import Parameter, ParameterItem, ParameterTree
from pyqtgraph.parametertree.parameterTypes import StrParameterItem
from pyqtgraph.widgets.DataFilterWidget import EnumFilterItem

from sdupy.utils import ignore_errors, make_async_using_thread, make_sync
from sdupy.widgets.helpers import paramtree_dump_params, paramtree_load_params
from . import register_widget

assert os.environ.get('PYQTGRAPH_QT_LIB') == 'PyQt5', \
    "This module is designed to work with PyQt5. Please set the env: PYQTGRAPH_QT_LIB=PyQt5"

class PgOneItem(pg.GraphicsView):
    def __init__(self, parent, view: pg.GraphicsWidget):
        super().__init__(parent)
        self.view = view
        self.setCentralItem(self.view)
        # FIXME: it's ugly hack but at least it's in one place and we don't break many code
        # self.visibilityChanged = parent.visibilityChanged
        # self.visibleRegion = parent.visibleRegion

    def visibleRegion2(self):
        # in pg.GraphicsView it returns always empty region
        return self.parentWidget().visibleRegion()

    @property
    def visibilityChanged(self):
        return self.parentWidget().visibilityChanged


@register_widget("pyqtgraph view box")
class PgViewBox(PgOneItem):
    def __init__(self, parent, name):
        super().__init__(parent, pg.ViewBox(lockAspect=True))


@register_widget("pyqtgraph layout")
class PgLayout(pg.GraphicsLayoutWidget):
    pass


@register_widget("pyqtgraph image")
class PgFigure(PgOneItem):
    def __init__(self, parent, name):
        super().__init__(parent, pg.PlotItem(lockAspect=True))
        self.view.setAspectLocked(True)

    def dump_state(self):
        return dict(
            view_state=self.view.saveState(),
        )

    def load_state(self, state: dict):
        if 'view_state' in state:
            self.view.restoreState(state['view_state'])


class PlotViewBox(pg.ViewBox):
    doubleClicked = QtCore.pyqtSignal(object)
    dragEnter = QtCore.pyqtSignal(object)  # QDragEnterEvent
    drop = QtCore.pyqtSignal(object)  # QDropEvent

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def wheelEvent(self, ev, axis=None):
        # zoom only horizontoally if Shift is pressed and vertically if Ctrl is pressed
        if axis is None:
            modifiers = QApplication.keyboardModifiers()
            if modifiers == Qt.ControlModifier:
                axis = 1
            elif modifiers == Qt.ShiftModifier:
                axis = 0

        super().wheelEvent(ev, axis)

    def mouseDoubleClickEvent(self, ev):
        super().mouseDoubleClickEvent(ev)
        self.doubleClicked.emit(ev)

    def dragEnterEvent(self, ev):
        self.dragEnter.emit(ev)
        # The event is not accepted here by default. The receiver of the signal must call ev.accept().

    def dropEvent(self, ev):
        self.drop.emit(ev)
        # The receiver should call ev.acceptProposedAction() if it handles the drop.


@register_widget("pyqtgraph plot")
class PgPlot(PgOneItem):
    dropped = QtCore.pyqtSignal(object, str)  # Emits data and mime_type

    def __init__(self, parent, name):
        vb = PlotViewBox(None, name=name)
        self.view: pg.PlotItem
        super().__init__(parent, pg.PlotItem(viewBox=vb))
        self.view.showGrid(x=True, y=True)
        self.mime_type_handler: Optional[Callable[[QMimeData], Optional[str]]] = None

        vb.dragEnter.connect(self.on_drag_enter)
        vb.drop.connect(self.on_drop)

    def on_drag_enter(self, ev: QDragEnterEvent):
        if not self.mime_type_handler:
            return
        accepted_mime_type = self.mime_type_handler(ev.mimeData())
        if accepted_mime_type:
            ev.acceptProposedAction()

    def on_drop(self, ev: QDropEvent):
        if not self.mime_type_handler:
            return
        accepted_mime_type = self.mime_type_handler(ev.mimeData())
        if accepted_mime_type:
            data = ev.mimeData().data(accepted_mime_type).data().decode()
            self.dropped.emit(data, accepted_mime_type)
            ev.acceptProposedAction()

    def dump_state(self):
        return dict(
            view_state=self.view.saveState(),
        )

    def load_state(self, state: dict):
        if 'view_state' in state:
            # preserve current linked views that was set programmatically
            view_state = state['view_state']
            linked_views = self.view.vb.state['linkedViews']
            linked_views = [i() if isinstance(i, weakref.ref) else i for i in linked_views]

            self.view.restoreState(view_state)

            if linked_views[0]:
                self.view.setXLink(linked_views[0])
            if linked_views[1]:
                self.view.setYLink(linked_views[1])



def index_to_str(index):
    res = []
    for i in index:
        if isinstance(i, slice):
            res.append("{}:{}".format(i.start if i.start is not None else "", i.stop if i.stop is not None else ""))
        else:
            res.append(str(i))
    return ','.join(res)


@register_widget("pyqtgraph image view")
class PgImage(pg.ImageView):
    def __init__(self, parent, name):
        super().__init__(parent, view=pg.PlotItem())
        self.view.setAspectLocked(True)
        self._show_cursor_proxy = None
        self.cursor_pos_label = None
        self.show_cursor_pos()
        self.visibilityChanged = parent.visibilityChanged  # FIXME we assume too much about our parent

        self.pos_label = QLabel(self)
        font = QFont()
        font.setWeight(75)
        font.setBold(True)
        self.pos_label.setFont(font)
        self.pos_label.setObjectName("pos_label")
        self.pos_label.setText('')
        self.ui.gridLayout.addWidget(self.pos_label, 2, 0, 2, 1)

    def show_cursor_pos(self, show=True):
        if self._show_cursor_proxy:
            self._show_cursor_proxy.disconnect()
            self._show_cursor_proxy = None
        if self.cursor_pos_label is not None:
            self.removeItem(self.cursor_pos_label)
            self.cursor_pos_label = None

        if show:
            @ignore_errors
            def mouseMoved(evt):
                view_point = self.view.vb.mapSceneToView(evt[0])
                text = "x,y = ({:6.1f}, {:6.1f})".format(view_point.x(), view_point.y())
                if self.image is not None and 'x' in self.axes and 'y' in self.axes:
                    item_point = self.imageItem.mapFromScene(evt[0])
                    ix = int(item_point.x())
                    iy = int(item_point.y())
                    if 0 <= ix < self.image.shape[self.axes['x']] and 0 <= iy < self.image.shape[self.axes['y']]:
                        index = [slice(None, None)] * len(self.image.shape)
                        index[self.axes['x']] = ix
                        index[self.axes['y']] = iy
                        if self.axes.get('t') is not None:
                            index[self.axes['t']] = self.currentIndex
                        val = self.image[tuple(index)]
                        text += "    data[{}] = {}".format(index_to_str(index), val)
                # self.cursor_pos_label.setText(text)
                self.pos_label.setText(text)
                # if all(isfinite(c) for c in [view_point.x(), view_point.y()]):
                #     self.cursor_pos_label.setPos(view_point)
                # else:
                #     self.cursor_pos_label.setPos(QPointF(0, 0))

            # self.cursor_pos_label = pg.TextItem(anchor=(0, 1))
            # self.addItem(self.cursor_pos_label)

        self._show_cursor_proxy = pg.SignalProxy(self.scene.sigMouseMoved, rateLimit=60, slot=mouseMoved)

    def dump_state(self):
        return dict(
            # view_state=self.getView().getState(),
            view_state=self.getView().saveState(),
            colormap=self.getHistogramWidget().gradient.saveState(),
            colormap_region=self.getHistogramWidget().region.getRegion()
        )

    def load_state(self, state: dict):
        if 'view_state' in state:
            # self.getView().setState(state['view_state'])
            self.getView().restoreState(state['view_state'])
        if 'colormap' in state:
            self.getHistogramWidget().gradient.restoreState(state['colormap'])
        if 'colormap_region' in state:
            self.getHistogramWidget().region.setRegion(state['colormap_region'])


@register_widget("pyqtgraph scatter plot")
class PgScatter(pg.ScatterPlotWidget):
    def __init__(self, parent, name):
        super().__init__(parent)
        self._show_cursor_proxy = None
        self.state_to_load = {}

        self.info_label = pg.TextItem(border=QColor(128, 128, 128))
        self.info_label.setPos(60, 60)
        self.info_label.setParentItem(self.plot.plotItem)
        self.show_info()

    def addNewAsEnum(self, name):
        f = self.filter
        item = EnumFilterItem(name, f.fields[name])
        f.addChild(item)
        return item

    def dump_state(self):
        filter_state = self.filter.saveState()
        filter_state['addList'] = list(filter_state['addList'])

        return dict(
            filter_state=filter_state,
            colormap_state=self.colorMap.saveState()
        )

    def show_info(self, show=True):
        if self._show_cursor_proxy:
            self._show_cursor_proxy.disconnect()
            self._show_cursor_proxy = None

        plot_item = self.plot.plotItem

        if show:
            @ignore_errors
            def mouseMoved(evt):
                view_point = plot_item.vb.mapSceneToView(evt[0])
                if self.scatterPlot is not None:
                    points = self.scatterPlot.scatter.pointsAt(view_point)
                    text = ''
                    for p in points:
                        for k, v in sorted(zip(self.fields.keys(), p.data())):
                            text += '{}: {}\n'.format(k, v)
                        text += '\n'
                    self.info_label.setText(text)
                    # print(text)

            self._show_cursor_proxy = pg.SignalProxy(plot_item.scene().sigMouseMoved, rateLimit=15, slot=mouseMoved)

            self.info_label.setVisible(True)
        else:
            self.info_label.setVisible(True)

    # def load_state(self, state: dict):
    #     self.state_to_load = state
    #
    # def _really_load_state(self):
    #     state = self.state_to_load
    #     if 'filter_state' in state:
    #         self.filter.restoreState(state['filter_state'])
    #     if 'colormap_state' in state:
    #         self.colorMap.restoreState(state['colormap_state'])
    #
    # def setData(self, data):
    #     super().setData(data)
    #     self._really_load_state()


@register_widget("pyqtgraph data tree")
class PgDataTree(pg.DataTreeWidget):
    def __init__(self, parent, name):
        super().__init__(parent)

    @property
    def visibilityChanged(self):
        return self.parentWidget().visibilityChanged

    @staticmethod
    def get_item_path(item: QTreeWidgetItem) -> str:
        res = []
        while isinstance(item, QTreeWidgetItem):
            res.append(item.text(0))
            item = item.parent()
        return "__".join(reversed(res))

    def setData(self, data, hideRoot=True):
        state = self.dump_state()
        super().setData(data, hideRoot=hideRoot)
        self.load_state(state)

    def dump_state(self):
        return dict(
            geometry=bytes(self.saveGeometry()).hex(),
            expanded={self.get_item_path(i): i.isExpanded() for i in
                              self.findItems("*", Qt.MatchWildcard | Qt.MatchRecursive)},
        )


    def load_state(self, state: dict):
        if 'geometry' in state:
            self.restoreGeometry(bytes.fromhex(state['geometry']))
        expaned = state.get('expanded', {})
        for i in self.findItems("*", Qt.MatchWildcard | Qt.MatchRecursive):
            path = self.get_item_path(i)
            if path in expaned:
                i.setExpanded(expaned[path])
            else:
                i.setExpanded(False)


@register_widget("pyqtgraph tree")
class PgTreeView(pg.TreeWidget):
    def __init__(self, parent, name):
        super().__init__(parent)

    @property
    def visibilityChanged(self):
        return self.parentWidget().visibilityChanged


class PathParameterItem(StrParameterItem):
    def __init__(self, param, depth):
        # param.opts['type'] = 'str'
        super().__init__(param, depth)

    def makeWidget(self):
        # opts = self.param.opts
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        widget.setLayout(layout)
        textbox = super().makeWidget()
        layout.addWidget(textbox)
        button = QPushButton('Browse...')
        # button.setFixedWidth(20)
        # button.setFixedHeight(20)

        layout.addWidget(button)
        button.clicked.connect(self.browse)

        # widget.setMaximumHeight(20)  ## set to match height of spin box and line edit
        widget.sigChanged = textbox.sigChanged
        widget.value = textbox.value
        widget.setValue = textbox.setValue
        self.widget = widget
        return widget

    @ignore_errors
    def browse(self, xx):
        file_dialog = QFileDialog()
        path = file_dialog.getExistingDirectory(directory=self.widget.value())
        if path:
            self.param.setValue(path)


class FilenameParameterItem(PathParameterItem):
    @ignore_errors
    def browse(self, xx):
        file_dialog = QFileDialog()
        if self.param.opts.get('save'):
            path = file_dialog.getSaveFileName(directory=self.widget.value())
        else:
            path = file_dialog.getOpenFileName(directory=self.widget.value())
        if path[0]:
            self.param.setValue(path[0])


class PathParameter(Parameter):
    itemClass = PathParameterItem


class FilenameParameter(Parameter):
    itemClass = FilenameParameterItem


class TaskParameterItem(ParameterItem):
    def __init__(self, param: Parameter, depth):
        super().__init__(param, depth)
        self.layoutWidget = QWidget()
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)

        self.start_stop_button = QPushButton()
        self.start_stop_button.setFixedHeight(20)
        self.start_stop_button.setFixedWidth(48)
        self.layout.addWidget(self.start_stop_button)
        self.start_stop_button.clicked.connect(self.buttonClicked)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(20)
        self.layout.addWidget(self.progress_bar)

        self.layoutWidget.setLayout(self.layout)
        # self.layout.addStretch()
        # param.sigNameChanged.connect(self.paramRenamed)
        # self.setText(0, '')
        self.param.sigValueChanged.connect(self.refresh)
        self.refresh(param, None)

    @ignore_errors
    def treeWidgetChanged(self):
        super().treeWidgetChanged()
        tree = self.treeWidget()
        if tree is None:
            return

        # tree.setFirstItemColumnSpanned(self, True)
        tree.setItemWidget(self, 1, self.layoutWidget)

    # def paramRenamed(self, param, name):
    #     self.start_stop_button.setText(name)

    def buttonClicked(self):
        self.param.start_or_stop()

    @ignore_errors
    def refresh(self, param: 'TaskParameter', val):
        self.progress_bar.setMaximum(1000)
        progress = param.progress
        status = param.status
        task = param.task
        if task is None:
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat('')
            self.start_stop_button.setText('start')
        elif task.done():
            if task is None:
                self.progress_bar.setFormat('')
            elif task.cancelled():
                self.progress_bar.setFormat('cancelled')
            elif task.exception():
                self.progress_bar.setFormat('error (see tooltip)')
                self.progress_bar.setToolTip('error: ' + str(task.exception()))

                try:
                    raise task.exception()
                except Exception:
                    logging.exception('task finished with error')


            else:
                self.progress_bar.setValue(1000)
                self.progress_bar.setFormat('finished')
            self.start_stop_button.setText('start')
        else:
            self.progress_bar.setFormat('%p% {}'.format(status))
            self.progress_bar.setValue(int(progress * 1000))
            self.start_stop_button.setText('cancel')


class TaskParameter(Parameter):
    """Used for displaying a button within the tree."""
    itemClass = TaskParameterItem

    # TODO: replace with some better control
    def __init__(self, func=None, **opts):
        super().__init__(**opts)
        self.func = func
        self.task = None  # type: asyncio.Task
        self.progress = None  # type: float
        self.status = None  # type: str
        # self.progress_param = self.addChild(dict(name="progress", type='float', readonly=True, value=0))
        # self.state_param = self.addChild(dict(name="state", type='str', readonly=True, value=0))
        # self.result_param = self.addChild(dict(name="result", type='text', readonly=True))

    @ignore_errors
    def start_or_stop(self):
        if self.task is not None and not self.task.done():
            self.task.cancel()
        else:
            self.task = asyncio.ensure_future(self.run_task())
            self.task.add_done_callback(self.task_finished_cbk)

    def task_finished_cbk(self, f):
        print('task finished')
        self.sigValueChanged.emit(self, None)

    async def run_task(self):
        self.progress = 0.0
        self.status = ''
        self.sigValueChanged.emit(self, None)
        await asyncio.sleep(0.001)
        if iscoroutinefunction(self.func):
            await self.func(self.checkpoint)
        else:
            await make_async_using_thread(self.func)(make_sync(self.checkpoint))
        self.sigValueChanged.emit(self, None)

    async def checkpoint(self, progress, status=None):
        if status != self.status or abs(progress - self.progress) >= 0.01:
            print("{:14.3f} {:5.1f}% {}".format(time.time(), progress * 100, status))
        self.progress = progress
        self.status = status
        self.sigValueChanged.emit(self, None)
        await asyncio.sleep(0.001)  # allow qt to repaint ans handle some queued events


class ActionParameterItem(ParameterItem):
    def __init__(self, param: Parameter, depth):
        super().__init__(param, depth)

        self.execute_button = QPushButton()
        self.execute_button.setFixedHeight(20)
        # self.execute_button.setFixedWidth(48)
        self.execute_button.clicked.connect(self.buttonClicked)
        self.execute_button.setText(param.name())

        self.label = QLabel()
        self.label.setFixedHeight(20)

    @ignore_errors
    def treeWidgetChanged(self):
        super().treeWidgetChanged()
        tree = self.treeWidget()
        if tree is None:
            return
        tree.setItemWidget(self, 0, self.execute_button)
        tree.setItemWidget(self, 1, self.label)

    def buttonClicked(self):
        try:
            res = self.param.func()
            self.label.setText('result: {}'.format(res))
        except Exception as e:
            self.label.setText('error (see tooltip)')
            self.label.setToolTip('error: ' + str(e))
            logging.exception('error during executing action {}'.format(self.param.name()))


class ActionParameter(Parameter):
    """Used for displaying a button within the tree."""
    itemClass = ActionParameterItem

    # TODO: replace with some better control
    def __init__(self, func=None, **opts):
        super().__init__(**opts)
        self.func = func


@register_widget('param tree')
class PgParamTree(QWidget):
    def __init__(self, parent, name):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.param_tree = ParameterTree(self)
        self.layout.addWidget(self.param_tree)

    def dump_state(self):
        return dict(params=paramtree_dump_params(self.param_tree))

    def load_state(self, state: dict):
        if 'params' in state:
            paramtree_load_params(self.param_tree, state['params'])

        pass


class LegendItemSample(ItemSample):
    SYMBOL = 's'
    SYMBOL_SIZE = 3

    def mouseClickEvent(self, event):
        """Use the mouseClick event to toggle the visibility of the plotItem
        """
        if event.button() == QtCore.Qt.MouseButton.MiddleButton:
            self.item.setSymbolSize(self.SYMBOL_SIZE)
            new_symbol = None if self.item.opts['symbol'] else self.SYMBOL
            self.item.setSymbol(new_symbol)

        super().mouseClickEvent(event)
