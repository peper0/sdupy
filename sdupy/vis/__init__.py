
from typing import Any, List, Tuple, Union, Sequence, Optional

import matplotlib.pyplot as plt
import numpy as np
from PyQt5.QtCore import QRectF, QPointF
from PyQt5.QtWidgets import QGraphicsItem

import sdupy
from sdupy.pyreactive import Var, Wrapped
from sdupy.pyreactive.decorators import reactive
from sdupy.pyreactive.wrappers.axes import ReactiveAxes
from sdupy.vis._helpers import make_graph_item_pg
from sdupy.vis.globals import global_refs
from ._helpers import image_to_mpl, image_to_pg, make_pg_image_item, levels_for, pg_hold_items
from sdupy.widgets import Figure, Slider, VarsTable, CheckBox, ComboBox
from sdupy.widgets.tables import ArrayTable
from sdupy.windows import WindowSpec


def widget(name: str, factory=None, window: WindowSpec = None):
    assert isinstance(name, str)
    return sdupy.window(window).obtain_widget(name, factory)


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
    image_name = kwargs.get('label')
    print('================shape', image.shape)
    i = ax.imshow(image_to_mpl(image, is_bgr), **kwargs)
    global_refs[(ax.__inner__, image_name)] = i
    return i


imshow = image_mpl


def plot_mpl(widget_name: str, *args, plot_fn='plot', window=None, **kwargs):
    ax = mpl_axes(name=widget_name, window=window)
    plot_name = kwargs.get('label')
    plot = getattr(ax, plot_fn)
    global_refs[(ax.__inner__, plot_name)] = plot(*args, **kwargs)


def draw_pg(widget_name: str, label, items: Sequence[Wrapped[QGraphicsItem]], window=None):
    from sdupy.widgets.pyqtgraph import PgPlot
    w = widget(widget_name, PgPlot, window=window)

    global_refs[(w, label)] = pg_hold_items(w.item, *items)


def image_pg(widget_name: str, image: Optional[np.ndarray], window=None, label=None, **kwargs):
    print("image_pg")
    #items = [make_pg_image_item(image_to_pg(image, is_bgr, True), **kwargs)] if image is not None else []
    items = [make_pg_image_item(image, **kwargs)] if image is not None else []
    draw_pg(widget_name, ('__image__', label), items, window=window)


def image_pg_adv(widget_name: str, image: np.ndarray, window=None, extent=None, **kwargs):
    from sdupy.widgets.pyqtgraph import PyQtGraphImage

    w = widget(widget_name, PyQtGraphImage, window=window)
    @reactive
    def set_image(image: np.ndarray, extent=None, **kwargs):
        set_image_args = kwargs
        set_image_args.setdefault('autoRange', False)
        set_image_args.setdefault('autoLevels', False)
        set_image_args.setdefault('autoHistogramRange', True)
        set_image_args.setdefault('axes', dict(y=0, x=1))
        axes = set_image_args['axes']
        if len(image.shape) == 3 and not ('t' in axes or 'c' in axes):
            #FIXME hack, what about rgb images?
            image = image[:, :, 0]
        w.setImage(image, **set_image_args)
        if extent is not None:
            xmin, xmax, ymin, ymax = extent
            w.imageItem.setRect(QRectF(QPointF(xmin, ymin), QPointF(xmax, ymax)))
        #w.imageItem.setAutoDownsample(True)

    # levels=levels_for(image),
    global_refs[(w, '__image__')] = set_image(image, extent, **kwargs)


def image_slice_pg_adv(widget_name: str, image: np.ndarray, window=None, **kwargs):
    return image_pg_adv(widget_name, image, window, axes=dict(t=0, y=1, x=2), **kwargs)


def graph_pg(widget_name: str, pos, adj, window=None, label=None, **kwargs):
    print("image_pg")
    #items = [make_pg_image_item(image_to_pg(image, is_bgr, True), **kwargs)] if image is not None else []
    items = [make_graph_item_pg(pos, adj, **kwargs)]
    draw_pg(widget_name, ('__graph__', label), items, window=window)
    return items[0]


graph = graph_pg


def data_tree_pg(widget_name: str, tree, window=None, **kwargs):
    from sdupy.widgets.pyqtgraph import PgDataTree
    w = widget(widget_name, PgDataTree, window=window)

    global_refs[(w)] = reactive(w.setData)(tree)


data_tree = data_tree_pg


def clear_variables(widget_name: str):
    vars_table = widget(widget_name, VarsTable)
    vars_table.clear()


def slider(widget_name: str, var: Wrapped=None, *, min=0, max=1, step=1, window=None):
    w = widget(widget_name, Slider, window)
    if var is not None:
        w.var = var
    global_refs[(w, 'set_params')] = reactive(w.set_params)(min, max, step)
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
