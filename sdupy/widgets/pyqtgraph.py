import asyncio
import logging
from math import isfinite

import pyqtgraph as pg
from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QFileDialog, QProgressBar, QVBoxLayout, QLabel
from pyqtgraph.parametertree import Parameter, ParameterItem, ParameterTree
from pyqtgraph.parametertree.parameterTypes import WidgetParameterItem

from sdupy.progress import Progress
from sdupy.utils import ignore_errors
from sdupy.widgets.helpers import paramtree_dump_params, paramtree_load_params
from . import register_widget


class PgOneItem(pg.GraphicsView):
    def __init__(self, parent, view):
        super().__init__(parent)
        self.view = view
        self.setCentralItem(self.view)
        #FIXME: it's ugly hack but at least it's in one place and we don't break many code
        #self.visibilityChanged = parent.visibilityChanged
        #self.visibleRegion = parent.visibleRegion

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


@register_widget("pyqtgraph plot")
class PgPlot(PgOneItem):
    def __init__(self, parent, name):
        super().__init__(parent, pg.PlotItem())


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
                #self.cursor_pos_label.setText(text)
                self.pos_label.setText(text)
                # if all(isfinite(c) for c in [view_point.x(), view_point.y()]):
                #     self.cursor_pos_label.setPos(view_point)
                # else:
                #     self.cursor_pos_label.setPos(QPointF(0, 0))

            #self.cursor_pos_label = pg.TextItem(anchor=(0, 1))
            #self.addItem(self.cursor_pos_label)

        self._show_cursor_proxy = pg.SignalProxy(self.scene.sigMouseMoved, rateLimit=60, slot=mouseMoved)

    def dump_state(self):
        return dict(
            #view_state=self.getView().getState(),
            view_state=self.getView().saveState(),
            colormap=self.getHistogramWidget().gradient.saveState(),
            colormap_region=self.getHistogramWidget().region.getRegion()
        )

    def load_state(self, state: dict):
        if 'view_state' in state:
            #self.getView().setState(state['view_state'])
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
                        for k, v in zip(self.fields.keys(), p.data()):
                            text += '{}: {}\n'.format(k, v)
                        text += '\n'
                    self.info_label.setText(text)
                    print(text)

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


class PathParameterItem(WidgetParameterItem):
    def __init__(self, param, depth):
        param.opts['type'] = 'str'
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
        #button.setFixedWidth(20)
        #button.setFixedHeight(20)

        layout.addWidget(button)
        button.clicked.connect(self.browse)

        #widget.setMaximumHeight(20)  ## set to match height of spin box and line edit
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
        #self.layout.addStretch()
        #param.sigNameChanged.connect(self.paramRenamed)
        #self.setText(0, '')
        self.param.sigValueChanged.connect(self.refresh)
        self.refresh(param, None)


    @ignore_errors
    def treeWidgetChanged(self):
        super().treeWidgetChanged()
        tree = self.treeWidget()
        if tree is None:
            return

        #tree.setFirstItemColumnSpanned(self, True)
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
            self.progress_bar.setValue(progress*1000)
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
        #self.progress_param = self.addChild(dict(name="progress", type='float', readonly=True, value=0))
        #self.state_param = self.addChild(dict(name="state", type='str', readonly=True, value=0))
        #self.result_param = self.addChild(dict(name="result", type='text', readonly=True))


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
        await self.func(self.checkpoint)
        self.sigValueChanged.emit(self, None)


    async def checkpoint(self, progress, status):
        self.progress = progress
        self.status = status
        self.sigValueChanged.emit(self, None)
        await asyncio.sleep(0.001)  # allow qt to repaint ans handle some queued events


class ActionParameterItem(ParameterItem):
    def __init__(self, param: Parameter, depth):
        super().__init__(param, depth)

        self.execute_button = QPushButton()
        self.execute_button.setFixedHeight(20)
        #self.execute_button.setFixedWidth(48)
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