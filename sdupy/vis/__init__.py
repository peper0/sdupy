
from typing import Any, List, Tuple, Union, Sequence, Optional

import matplotlib.pyplot as plt
import numpy as np
from PyQt5.QtWidgets import QGraphicsItem

import sdupy
from sdupy.reactive import Var, WrapperInterface
from sdupy.reactive.decorators import reactive
from sdupy.reactive.wrappers.axes import ReactiveAxes
from ._helpers import image_to_rgb, pg_hold_item, image_to_pg, make_pg_image_item, levels_for, pg_hold_items
from sdupy.widgets import Figure, Slider, VarsTable, CheckBox, ComboBox
from sdupy.widgets.tables import ArrayTable
from sdupy.windows import WindowSpec

global_refs = {}


def widget(name: str, factory=None, window: WindowSpec = None):
    assert isinstance(name, str)
    return sdupy.window(window).obtain_widget(name, factory)


# TODO: add option for name=None that returns the last axes used or the new one (if none was used yet)
def mpl_axes(name: str, window: WindowSpec = None) -> Union[ReactiveAxes, plt.Axes]:
    return ReactiveAxes(widget(name, Figure, window=window).axes)


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
    global_refs[(ax.__inner__, image_name)] = ax.imshow(image_to_rgb(image, is_bgr), **kwargs)


@reactive
def draw_pg(widget_name: str, label, items: Sequence[QGraphicsItem], window=None):
    from sdupy.widgets.pyqtgraph import PgPlot
    w = widget(widget_name, PgPlot, window=window)

    global_refs[(w, label)] = pg_hold_items(w.item, items)


@reactive
def image_pg(widget_name: str, image: Optional[np.ndarray], is_bgr=True, window=None, label=None, **kwargs):
    items = [make_pg_image_item(image_to_pg(image, is_bgr, True), **kwargs)] if image is not None else []
    draw_pg(widget_name, ('__image__', label), items)


@reactive
def image_pg_adv(widget_name: str, image: np.ndarray, is_bgr=True, window=None, **kwargs):
    from sdupy.widgets.pyqtgraph import PyQtGraphImage

    w = widget(widget_name, PyQtGraphImage, window=window)
    w.imageItem.setAutoDownsample(True)
    global_refs[(w, '__image__')] = reactive(w.setImage)(image_to_pg(image, is_bgr, False),  #FIXME why no flip here?
                                                     autoRange=False,
                                                     autoLevels=False,
                                                     levels=levels_for(image),
                                                     )


imshow = image_mpl
display_image = image_mpl


def clear_variables(widget_name: str):
    vars_table = widget(widget_name, VarsTable)
    vars_table.clear()


def slider(widget_name: str, var: WrapperInterface, *, min, max, step=1, window=None):
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
    return widget.data_var


def checkbox(widget_name: str, var: WrapperInterface=None, *, window=None):
    w = widget(widget_name, CheckBox, window)
    if var is not None:
        w.var = var
    return w.var


def var_in_table(widget_name: str, var_name: str, var: WrapperInterface, *, to_value=eval, window=None):
    assert isinstance(widget_name, str)
    var = var if var is not None else Var()  # fixme: check if there is already such a var
    vars_table = widget(widget_name, VarsTable, window)
    vars_table.insert_var(var_name, var, to_value=to_value)
    return var


def array_table(widget_name: str, var: WrapperInterface=None, *, window=None):
    w = widget(widget_name, ArrayTable, window)
    if var is None:
        var = sdupy.var(np.zeros((2, 3)))  # fixme
    w.var = var
    return w.var
