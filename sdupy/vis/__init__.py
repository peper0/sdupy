import gc
from functools import wraps
from typing import Any, List, Tuple, Optional, Callable

import matplotlib.pyplot as plt
import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QRectF, QPointF
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QGraphicsItem, QDockWidget, QWidget, QMenu, QAction, QMenuBar, QTreeWidgetItem
from pyqtgraph.parametertree import ParameterTree, Parameter

import sdupy
from sdupy.pyreactive import Var, Wrapped
from sdupy.pyreactive.decorators import reactive
from sdupy.pyreactive.notifier import ScopedName
from sdupy.pyreactive.utils import bind_vars
from sdupy.pyreactive.wrappers.axes import ReactiveAxes
from sdupy.utils import ignore_errors
from sdupy.vis._helpers import make_graph_item_pg, set_zvalue, make_plot_item_pg, set_scatter_data_pg, \
    pg_hold_items_unroll, make_histogram_item_pg, make_bargraph_item_pg
from sdupy.vis.globals import global_refs, store_global_ref
from sdupy.widgets import Figure, Slider, VarsTable, CheckBox, ComboBox
from sdupy.widgets.common.qt_property_var import QtSignaledVar
from sdupy.widgets.helpers import paramtree_get_root_parameters, trigger_if_visible
from sdupy.widgets.pyqtgraph import PgPlot, PgParamTree, TaskParameter, PgScatter, ActionParameter, LegendItemSample
from sdupy.widgets.tables import ArrayTable
from sdupy.windows import WindowSpec
from ._helpers import image_to_mpl, image_to_pg, make_pg_image_item, levels_for, pg_hold_items
from .utils import *

Place = str
"""
A placement of a widget.
* `str` - a name of a widget in the current window
* `QWidget` - a specific widget
* more may be added in the future, e.g. a pair of window and widget

"""

def widget_and_dock(name: str, factory=None, window: WindowSpec = None) -> (QWidget, QDockWidget):
    isinstance(name, str)
    return sdupy.window(window).obtain_widget(name, factory)

def widget(place: Place, factory=None, window: WindowSpec = None) -> QWidget:
    if isinstance(place, QWidget):
        return place
    elif isinstance(place, str):
        return widget_and_dock(place, factory, window)[0]
    else:
        raise TypeError("place should be str or QWidget, got {}".format(type(place)))


def dock_widget(name: str, factory=None, window: WindowSpec = None) -> QDockWidget:
    return widget_and_dock(name, factory, window)[1]


# TODO: add option for name=None that returns the last axes used or the new one (if none was used yet)
def mpl_axes(place: Place, window: WindowSpec = None) -> Union[ReactiveAxes, plt.Axes]:
    return ReactiveAxes(widget(place, Figure, window=window).axes)


axes = mpl_axes


def image_mpl(place: Place, image: Wrapped[np.ndarray], is_bgr=True, window=None, **kwargs):
    """
    :param name: Unique identifier among all widgets. If such widget doesn't exist, it will be created.
    :param image: Any image that matplotlib can plot with imshow.
    :param is_bgr: If the image has 3 components, treat them as Blue, Green, Red in this order (Red Green Blue
                    otherwise)
    :return:
    """
    ax = mpl_axes(place=place, window=window)
    w = widget(place=place, window=window)
    image_name = kwargs.get('label')
    i = ax.imshow(image_to_mpl(image, is_bgr), **kwargs)
    global_refs[(ax.__inner__, image_name)] = trigger_if_visible(i, ax.__inner__.get_figure().canvas.parentWidget())
    return i


imshow = image_mpl


def plot_mpl(widget_name: Place, *args, plot_fn='plot', window=None, **kwargs):
    ax = mpl_axes(place=widget_name, window=window)
    plot_name = kwargs.get('label')
    plot = getattr(ax, plot_fn)
    global_refs[(ax.__inner__, plot_name)] = trigger_if_visible(plot(*args, **kwargs),
                                                              ax.__inner__.get_figure().canvas.parentWidget())
    gc.collect()

    if plot_name:
        ax.legend()


def draw_pg(place: Place, label, items: Sequence[Wrapped[QGraphicsItem] | QGraphicsItem], zvalue=None, window=None):
    from sdupy.widgets.pyqtgraph import PgFigure
    w = widget(place, PgFigure, window=window)
    global_refs[(w, label)] = trigger_if_visible(pg_hold_items_unroll(w.view, items, zvalue=zvalue), w)


def image_pg(place: Place, image: Optional[np.ndarray], window=None, label=None, zvalue=None, **kwargs):
    with ScopedName(name=place+('.'+label if label else '')):
        items = [make_pg_image_item(image, **kwargs)]
        draw_pg(place, ('__image__', label), items, zvalue=zvalue, window=window)


def image_pg_adv(place: Place, image: np.ndarray, window=None, extent=None, **kwargs):
    from sdupy.widgets.pyqtgraph import PgImage

    w = widget(place, PgImage, window=window)

    @reactive
    def set_image(image: np.ndarray, extent=None, **kwargs):
        set_image_args = kwargs
        set_image_args.setdefault('autoRange', False)
        set_image_args.setdefault('autoLevels', False)
        set_image_args.setdefault('autoHistogramRange', True)
        if image is None:
            image = np.zeros((1, 1))
        if 'axes' not in set_image_args:
            if image.ndim == 4:
                set_image_args['axes'] = dict(t=0, y=1, x=2, c=3)
            elif image.ndim == 3:
                set_image_args['axes'] = dict(y=0, x=1, c=2)
            elif image.ndim == 2:
                set_image_args['axes'] = dict(y=0, x=1)
        # set_image_args.setdefault('axes', dict(y=0, x=1))
        # axes = set_image_args['axes']
        # if len(image.shape) == 3 and not ('t' in axes or 'c' in axes):
        #     #FIXME hack, what about rgb images?
        #     image = image[:, :, 0]
        w.setImage(image, **set_image_args)
        if extent is not None:
            xmin, xmax, ymin, ymax = extent
            w.imageItem.setRect(QRectF(QPointF(xmin, ymin), QPointF(xmax, ymax)))
        #w.imageItem.setAutoDownsample(True)

    # levels=levels_for(image),
    global_refs[(w, '__image__')] = trigger_if_visible(set_image(image, extent, **kwargs), w)


def image_slice_pg_adv(place: Place, image: np.ndarray, window=None, **kwargs):
    return image_pg_adv(place, image, window, axes=dict(t=0, y=1, x=2), **kwargs)


def graph_pg(place: Place, pos, adj, window=None, label=None, zvalue=None, **kwargs):
    print("image_pg")
    items = [make_graph_item_pg(pos, adj, **kwargs)]
    draw_pg(place, ('__graph__', label), items, window=window, zvalue=zvalue)
    return items[0]


graph = graph_pg




def plot_pg(place: Place, *args, label=None, window=None, **kwargs):
    w = widget(place, PgPlot, window=window)
    if label and "name" not in kwargs:
        w.view.addLegend(sampleType=LegendItemSample)
        kwargs["name"] = label

    plot_item = make_plot_item_pg(w.view, *args, **kwargs)
    r = trigger_if_visible(plot_item, w)
    store_global_ref((w, label), r)
    return r

def histogram_pg(place: Place, *args, label=None, window=None, **kwargs):
    w = widget(place, PgPlot, window=window)
    plot_item = make_histogram_item_pg(w.view, *args, **kwargs)
    r = trigger_if_visible(plot_item, w)
    store_global_ref((w, label), r)
    return r

def bargraph_pg(place: Place, *args, label=None, window=None, **kwargs):
    w = widget(place, PgPlot, window=window)
    plot_item = make_bargraph_item_pg(w.view, *args, **kwargs)
    r = trigger_if_visible(plot_item, w)
    store_global_ref((w, label), r)
    return r

def scatter_pg(place: Place, data, label=None, window=None):
    w = widget(place, PgScatter, window=window)
    global_refs[(w, label)] = trigger_if_visible(set_scatter_data_pg(w, data), w)
    return global_refs[(w, label)]


def data_tree_pg(place: Place, tree, window=None, **kwargs):
    from sdupy.widgets.pyqtgraph import PgDataTree
    w = widget(place, PgDataTree, window=window)
    assert isinstance(w, PgDataTree)
    global_refs[(w)] = trigger_if_visible(reactive(w.setData)(tree), w)


data_tree = data_tree_pg


def clear_variables(place: Place):
    vars_table = widget(place, VarsTable)
    vars_table.clear()


def slider(place: Place, var: Wrapped=None, *, min=0, max=1, step=1, value=None, window=None):

    w = widget(place, Slider, window)
    if var is not None:
        w.var = var
    global_refs[(w, 'set_params')] = volatile(reactive(w.set_params)(min, max, step))
    if value is not None:
        w.var.__inner__ = value
    return w.var


def combo(place: Place, *, choices: List[Union[Any, Tuple[str, Any]]], window=None):
    w = widget(place, ComboBox, window)
    global_refs[(w, 'set_choices')] = volatile(reactive(w.set_choices)(choices))
    # if widget.combo.currentIndex() < 0:
    #     widget.combo.setCurrentIndex(0)
    return w.data_var


def checkbox(place: Place, var: Wrapped=None, *, window=None):
    w = widget(place, CheckBox, window)
    if var is not None:
        w.var = var
    return w.var


def var_in_table(place: Place, var_name: str, var: Wrapped, *, to_value=eval, window=None):
    assert isinstance(place, str)
    var = var if var is not None else Var()  # fixme: check if there is already such a var
    vars_table = widget(place, VarsTable, window)
    vars_table.insert_var(var_name, var, to_value=to_value)
    return var


def array_table(place: Place, var: Wrapped=None, *, format:str=None, window=None):
    w = widget(place, ArrayTable, window)
    if var is None:
        var = sdupy.var(np.zeros((2, 3)))  # fixme
    w.var = var
    if format is not None:
        w.format = format
    return w.var


def _paramtree_find_child(parent, child_name):
    if isinstance(parent, ParameterTree):
        root = parent.invisibleRootItem()  # type: QTreeWidgetItem
        for i in paramtree_get_root_parameters(parent):
            if i.name() == child_name:
                return i
        return None
    elif isinstance(parent, Parameter):
        return parent.names.get(child_name)
    raise Exception("parent has type {}".format(type(parent)))


def _paramtree_add_child(parent, param):
    if isinstance(parent, ParameterTree):
        root = parent.invisibleRootItem()  # type: QTreeWidgetItem
        for i in range(root.childCount()):
            child = root.child(i)
            if child is not None and child.text(0) == param.name():
                root.removeChild(child)
        parent.addParameters(param)
        return None
    elif isinstance(parent, Parameter):
        child = parent.names.get(param.name())  # type: Parameter
        if child is not None:
            grandchildren = child.children()
            parent.removeChild(child)
            param.addChildren(grandchildren)
        new_child = parent.addChild(param)
        return new_child
    raise Exception("parent has type {}".format(type(parent)))


def param_in_paramtree(place: Place, param_path: Sequence[str], param, *, window=None):
    parent = group_in_paramtree(place, param_path, window)

    _paramtree_add_child(parent, param)


def group_in_paramtree(place, param_path, window=None):
    assert isinstance(place, Place)
    param_tree = widget(place, PgParamTree, window).param_tree  # type: ParameterTree
    parent = param_tree
    # for i in range(len(param_path)-1):
    for i in param_path:
        child = _paramtree_find_child(parent, i)
        if child is None:
            child = Parameter.create(name=i, type='group')
            _paramtree_add_child(parent, child)
        parent = child
    return parent


class PgParamVar(QtSignaledVar):
    def __init__(self, param: Parameter):
        super().__init__(param.sigValueChanged)
        self.param = param
        self.param.sigValueChanged.connect(self.test)

    def test(self):
        print("{}, changed".format(self))

    def set(self, value):
        self.param.setValue(value)

    def get(self):
        return self.param.value()


def var_in_paramtree(place: Place, param_path: Sequence[str], param, var: Wrapped = None, *, window=None):
    param_in_paramtree(place, param_path, param, window=window)

    pg_param_var = PgParamVar(param)
    if var is None:
        var = pg_param_var
    else:
        store_global_ref((place, tuple(param_path)), bind_vars(var, pg_param_var))

    return var


def task_in_paramtree(place: Place, param_path: Sequence[str],
                      func: Callable[['Checkpoint'], Any] = None, *,
                      window=None):
    *parent_path, name = param_path
    param = TaskParameter(name=name, func=func)
    param_in_paramtree(place, parent_path, param, window=window)
    return param


def action_in_paramtree(place: Place, param_path: Sequence[str], func: Callable[[], Any] = None, *,
                        window=None):
    *parent_path, name = param_path
    param = ActionParameter(name=name, func=func)
    param_in_paramtree(place, parent_path, param, window=window)
    return param


def decor_task_in_paramtree(place: Place, param_path: Sequence[str], *, window=None):
    @wraps(task_in_paramtree)
    def f(func):
        task_in_paramtree(place, param_path, func, window=window)
        return func

    return f


def decor_action_in_paramtree(place: Place, param_path: Sequence[str], *, window=None):
    @wraps(action_in_paramtree)
    def f(func):
        action_in_paramtree(place, param_path, func, window=window)
        return func

    return f


def combo_in_paramtree(place: Place, param_path: Sequence[str], choices, var: Wrapped = None, *, window=None):
    *parent_path, name = param_path
    param = Parameter.create(name=name, type='list')
    res = var_in_paramtree(place, parent_path, param=param, var=var, window=window)
    global_refs[(place, tuple(param_path), 'limits')] = volatile(reactive(param.setLimits)(choices))
    return res


def checkbox_in_paramtree(place: Place, param_path: Sequence[str], value=None, var: Wrapped = None, *, window=None):
    assert not isinstance(param_path, str)
    *parent_path, name = param_path
    param = Parameter.create(name=name, type='bool', value=value, default=value)
    res = var_in_paramtree(place, parent_path, param=param, var=var, window=window)
    return res


def text_in_paramtree(place: Place, param_path: Sequence[str], multiline=False, value=None, var: Wrapped = None, *,
                      window=None, **kwargs):
    *parent_path, name = param_path
    return var_in_paramtree(place, parent_path,
                            param=Parameter.create(name=name, type='text' if multiline else 'str',
                                                   value=value, default=value, **kwargs),
                            var=var, window=window)


def int_in_paramtree(place: Place, param_path: Sequence[str], value=None, var: Wrapped = None, *,
                      window=None, **kwargs):
    *parent_path, name = param_path
    return var_in_paramtree(place, parent_path,
                            param=Parameter.create(name=name, type='int', decimals=7, value=value, default=value, **kwargs),
                            var=var, window=window)


def float_in_paramtree(place: Place, param_path: Sequence[str], value=None, var: Wrapped = None, window=None,
                       **kwargs):
    *parent_path, name = param_path
    return var_in_paramtree(place, parent_path,
                            param=Parameter.create(name=name, type='float', value=value, default=value,
                                                   **kwargs),
                            var=var, window=window)


def add_action_to_menu(menu: Union[QMenu, QMenuBar], path: Sequence[str], new_action: QAction):
    actions = {action.text(): action for action in menu.actions()}
    if path:
        path_head, *path_rest = path
        action = actions.get(path_head)

        if action:
            submenu = action.menu()
        else:
            submenu = menu.addMenu(menu.addMenu(path_head)).menu()
        add_action_to_menu(submenu, path_rest, new_action)
    else:
        action = actions.get(new_action.text())
        if action:
            menu.removeAction(action)
        menu.addAction(new_action)


def action_in_menu(path: Sequence[str], func: Callable[[], Any] = None,
                   shortcut: Union[QKeySequence, QKeySequence.StandardKey, str, int] = None,
                   *, window=None):
    qwindow = sdupy.window(window)
    #menu = qwindow.menuBar().findChild(QMenu)  # type: QMenu
    menu = qwindow.menuBar()

    action = QAction(parent=qwindow)

    *subpath, title = path
    action.setText(title)
    if shortcut:
        action.setShortcut(shortcut)

    def func2():  # if we pass ignore_errors(func) to connect, this function will be given some argument
        return ignore_errors(func)()

    action.triggered.connect(func2)

    add_action_to_menu(menu, subpath, action)


def decor_action_in_menu(path: Sequence[str],
                         shortcut: Union[QKeySequence, QKeySequence.StandardKey, str, int] = None,
                         *, window=None):
    @wraps(action_in_menu)
    def f(func):
        action_in_menu(path, func, shortcut, window=window)
        return func

    return f


def set_titles_mpl(place: Place, title=None, x=None, y=None):
    if title is not None:
        sdupy.unwrap(vis.axes(place)).set_title(title)
    if x is not None:
        sdupy.unwrap(vis.axes(place)).set_xlabel(x)
    if y is not None:
        sdupy.unwrap(vis.axes(place)).set_ylabel(y)
    vis.widget(place).tight_layout()



def pg_extent(place: Place, name, value=(0, 0, 1, 1)):
    extent_xy = value[0], value[2]
    extent_wh = value[1] - value[0], value[3] - value[2]
    roi = pg.ROI(extent_xy, extent_wh)
    vis.draw_pg(place, name, [roi])
    vis.pg_roi_add_8handles(roi)

    v = sdupy.var(value)

    def refr():
        rect = roi.boundingRect().translated(roi.pos())
        v.set((rect.left(), rect.right(), rect.top(), rect.bottom()))

    roi.sigRegionChangeFinished.connect(refr)

    # FIXME: add support for setting
    # def set_roi_to_full_extent():
    #     extent = round_extent(calc_extent(stitcher.homos, ref_image_hw))
    #
    #     from PyQt5.QtCore import QPointF
    #     roi.setPos(QPointF(extent[0], extent[2]))
    #     roi.setSize(QPointF(extent[1] - extent[0], extent[3] - extent[2]))

    return v

def pg_vline(place: Place, name, var=0, eager=False, **kwargs):
    line = pg.InfiniteLine(angle=90, **kwargs)
    vis.draw_pg(place, name, [line])
    # vis.pg_roi_add_8handles(roi)

    from sdupy.pyreactive import Var
    if not isinstance(var, Var):
        var = sdupy.var(var)

    def refr():
        x, _ = line.pos()
        if x != var.__inner__:
            var.set(x)

    if eager:
        line.sigPositionChanged.connect(refr)
    else:
        line.sigPositionChangeFinished.connect(refr)

    @reactive
    def set_to_var(x):
        if x != line.pos()[0]:
            line.setPos(x)

    vis.global_refs[(vis.widget(place), name + "__setter")] = vis.trigger_if_visible(set_to_var(var),
                                                                                      vis.widget(place))
    return var