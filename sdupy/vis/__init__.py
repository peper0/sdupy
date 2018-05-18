from typing import Any, List, Tuple, Union, Sequence, Optional, Callable, Coroutine

import matplotlib.pyplot as plt
import numpy as np
from PyQt5.QtCore import QRectF, QPointF
from PyQt5.QtWidgets import QGraphicsItem, QDockWidget, QWidget
from PyQt5.QtWidgets import QTreeWidgetItem
from pyqtgraph.parametertree import ParameterTree, Parameter

import sdupy
from sdupy.pyreactive import Var, Wrapped
from sdupy.pyreactive.decorators import reactive
from sdupy.pyreactive.notifier import ScopedName
from sdupy.pyreactive.var import volatile
from sdupy.pyreactive.wrappers.axes import ReactiveAxes
from sdupy.vis._helpers import make_graph_item_pg, set_zvalue, make_plot_item_pg, set_scatter_data_pg
from sdupy.widgets.hepers import trigger_if_visible
from sdupy.vis.globals import global_refs
from sdupy.progress import Progress
from sdupy.widgets.common.qt_property_var import QtSignaledVar
from sdupy.widgets.pyqtgraph import PgPlot, PgParamTree, TaskParameter, PgScatter
from ._helpers import image_to_mpl, image_to_pg, make_pg_image_item, levels_for, pg_hold_items
from sdupy.widgets import Figure, Slider, VarsTable, CheckBox, ComboBox
from sdupy.widgets.tables import ArrayTable
from sdupy.windows import WindowSpec


def widget_and_dock(name: str, factory=None, window: WindowSpec = None):
    assert isinstance(name, str)
    return sdupy.window(window).obtain_widget(name, factory)


def widget(name: str, factory=None, window: WindowSpec = None) -> QWidget:
    return widget_and_dock(name, factory, window)[0]


def dock_widget(name: str, factory=None, window: WindowSpec = None) -> QDockWidget:
    return widget_and_dock(name, factory, window)[1]


# TODO: add option for name=None that returns the last axes used or the new one (if none was used yet)
def mpl_axes(name: str, window: WindowSpec = None) -> Union[ReactiveAxes, plt.Axes]:
    return ReactiveAxes(widget(name, Figure, window=window).axes)


axes = mpl_axes


def image_mpl(widget_name: str, image: np.ndarray, is_bgr=True, window=None, **kwargs):
    """
    :param name: Unique identifier among all widgets. If such widget doesn't exist, it will be created.
    :param image: Any image that matplotlib can plot with imshow.
    :param is_bgr: If the image has 3 components, treat them as Blue, Green, Red in this order (Red Green Blue
                    otherwise)
    :return:
    """
    ax = mpl_axes(name=widget_name, window=window)
    w = widget(name=widget_name, window=window)
    image_name = kwargs.get('label')
    print('================shape', image.shape)
    i = ax.imshow(image_to_mpl(image, is_bgr), **kwargs)
    global_refs[(ax.__inner__, image_name)] = trigger_if_visible(i, ax.__inner__.get_figure().canvas.parentWidget())
    return i


imshow = image_mpl


def plot_mpl(widget_name: str, *args, plot_fn='plot', window=None, **kwargs):
    ax = mpl_axes(name=widget_name, window=window)
    plot_name = kwargs.get('label')
    plot = getattr(ax, plot_fn)
    global_refs[(ax.__inner__, plot_name)] = trigger_if_visible(plot(*args, **kwargs),
                                                              ax.__inner__.get_figure().canvas.parentWidget())


def draw_pg(widget_name: str, label, items: Sequence[Wrapped[QGraphicsItem]], zvalue=None, window=None):
    from sdupy.widgets.pyqtgraph import PgFigure
    w = widget(widget_name, PgFigure, window=window)

    global_refs[(w, label)] = trigger_if_visible(pg_hold_items(w.view, *items, zvalue=zvalue), w)


def image_pg(widget_name: str, image: Optional[np.ndarray], window=None, label=None, zvalue=None, **kwargs):
    with ScopedName(name=widget_name+('.'+label if label else '')):
        items = [make_pg_image_item(image, **kwargs)]
        if items[0] is None:
            items = []
        draw_pg(widget_name, ('__image__', label), items, zvalue=zvalue, window=window)


def image_pg_adv(widget_name: str, image: np.ndarray, window=None, extent=None, **kwargs):
    from sdupy.widgets.pyqtgraph import PgImage

    w = widget(widget_name, PgImage, window=window)

    @reactive
    def set_image(image: np.ndarray, extent=None, **kwargs):
        set_image_args = kwargs
        set_image_args.setdefault('autoRange', False)
        set_image_args.setdefault('autoLevels', False)
        set_image_args.setdefault('autoHistogramRange', True)
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


def image_slice_pg_adv(widget_name: str, image: np.ndarray, window=None, **kwargs):
    return image_pg_adv(widget_name, image, window, axes=dict(t=0, y=1, x=2), **kwargs)


def graph_pg(widget_name: str, pos, adj, window=None, label=None, **kwargs):
    print("image_pg")
    items = [make_graph_item_pg(pos, adj, **kwargs)]
    draw_pg(widget_name, ('__graph__', label), items, window=window)
    return items[0]


graph = graph_pg


def plot_pg(widget_name: str, *args, label=None, window=None, **kwargs):
    w = widget(widget_name, PgPlot, window=window)
    global_refs[(w, label)] = trigger_if_visible(make_plot_item_pg(w.view, *args, **kwargs), w)
    return global_refs[(w, label)]


def scatter_pg(widget_name: str, data, label=None, window=None):
    w = widget(widget_name, PgScatter, window=window)
    global_refs[(w, label)] = trigger_if_visible(set_scatter_data_pg(w, data), w)
    return global_refs[(w, label)]


def data_tree_pg(widget_name: str, tree, window=None, **kwargs):
    from sdupy.widgets.pyqtgraph import PgDataTree
    w = widget(widget_name, PgDataTree, window=window)

    global_refs[(w)] = trigger_if_visible(reactive(w.setData)(tree), w)


data_tree = data_tree_pg


def clear_variables(widget_name: str):
    vars_table = widget(widget_name, VarsTable)
    vars_table.clear()


def slider(widget_name: str, var: Wrapped=None, *, min=0, max=1, step=1, window=None):

    w = widget(widget_name, Slider, window)
    if var is not None:
        w.var = var
    global_refs[(w, 'set_params')] = volatile(reactive(w.set_params)(min, max, step))
    return w.var


def combo(widget_name: str, *, choices: List[Union[Any, Tuple[str, Any]]], window=None):
    w = widget(widget_name, ComboBox, window)
    global_refs[(w, 'set_choices')] = reactive(w.set_choices)(choices)
    # if widget.combo.currentIndex() < 0:
    #     widget.combo.setCurrentIndex(0)
    return w.data_var


def checkbox(widget_name: str, var: Wrapped=None, *, window=None):
    w = widget(widget_name, CheckBox, window)
    if var is not None:
        w.var = var
    return w.var


def var_in_table(widget_name: str, var_name: str, var: Wrapped, *, to_value=eval, window=None):
    assert isinstance(widget_name, str)
    var = var if var is not None else Var()  # fixme: check if there is already such a var
    vars_table = widget(widget_name, VarsTable, window)
    vars_table.insert_var(var_name, var, to_value=to_value)
    return var


def array_table(widget_name: str, var: Wrapped=None, *, format:str=None, window=None):
    w = widget(widget_name, ArrayTable, window)
    if var is None:
        var = sdupy.var(np.zeros((2, 3)))  # fixme
    w.var = var
    if format is not None:
        w.format = format
    return w.var


def paramtree_get_root_parameters(pt: ParameterTree) -> Sequence[Parameter]:
    root = pt.invisibleRootItem()
    return [root.child(i).param for i in range(root.childCount())]


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
            if root.child(i).text(0) == param.name():
                root.removeChild(i)
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


def param_in_paramtree(widget_name: str, param_path: Sequence[str], param, *, window=None):
    assert isinstance(widget_name, str)
    param_tree = widget(widget_name, PgParamTree, window).param_tree   # type: ParameterTree
    parent = param_tree
    #for i in range(len(param_path)-1):
    for i in param_path:
        child = _paramtree_find_child(parent, i)
        if child is None:
            child = Parameter.create(name=i, type='group')
            _paramtree_add_child(parent, child)
        parent = child

    _paramtree_add_child(parent, param)


class PgParamVar(QtSignaledVar):
    def __init__(self, param: Parameter):
        super().__init__(param.sigValueChanged)
        self.param = param

    def set(self, value):
        self.param.setValue(value)

    def get(self):
        return self.param.value()


def var_in_paramtree(widget_name: str, param_path: Sequence[str], param, var: Wrapped = None, *, window=None):
    param_in_paramtree(widget_name, param_path, param, window=window)

    if var is None:
        var = PgParamVar(param)
    else:
        # TODO: bind current parameter with a PgParamVar
        raise NotImplementedError()

    return var


def task_in_paramtree(widget_name: str, param_path: Sequence[str], func: Callable[[Progress], Coroutine] = None, *,
                      window=None):
    *parent_path, name = param_path
    param = TaskParameter(name=name, func=func)
    param_in_paramtree(widget_name, parent_path, param, window=window)
    return param


def combo_in_paramtree(widget_name: str, param_path: Sequence[str], choices, var: Wrapped = None, *, window=None):
    *parent_path, name = param_path
    param = Parameter.create(name=name, type='list')
    res = var_in_paramtree(widget_name, parent_path, param=param, var=var, window=window)
    global_refs[(widget_name, tuple(param_path), 'limits')] = volatile(reactive(param.setLimits)(choices))
    return res


def text_in_paramtree(widget_name: str, param_path: Sequence[str], multiline=False, var: Wrapped = None, *,
                      window=None):
    *parent_path, name = param_path
    return var_in_paramtree(widget_name, parent_path,
                            param=Parameter.create(name=name, type='text' if multiline else 'str'),
                            var=var, window=window)


def int_in_paramtree(widget_name: str, param_path: Sequence[str], value=None, var: Wrapped = None, *,
                      window=None):
    *parent_path, name = param_path
    return var_in_paramtree(widget_name, parent_path,
                            param=Parameter.create(name=name, type='int', decimals=7, value=value, default=value),
                            var=var, window=window)


def float_in_paramtree(widget_name: str, param_path: Sequence[str], step=None, value=None, var: Wrapped = None, *,
                      window=None):
    *parent_path, name = param_path
    return var_in_paramtree(widget_name, parent_path,
                            param=Parameter.create(name=name, type='float', step=step, value=value, default=value),
                            var=var, window=window)