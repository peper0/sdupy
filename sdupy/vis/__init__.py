
from typing import Any, List, Tuple, Union

import cv2
import matplotlib.pyplot as plt
import numpy as np

import sdupy
from sdupy.reactive import Var, WrapperInterface
from sdupy.reactive.decorators import reactive
from sdupy.reactive.var import Proxy
from sdupy.reactive.wrappers.axes import ReactiveAxes
from sdupy.widgets import ComboBox, Figure, Slider, VarsTable
from sdupy.windows import WindowSpec


def widget(name: str, factory=None, window: WindowSpec = None):
    assert isinstance(name, str)
    return sdupy.window(window).obtain_widget(name, factory)


# TODO: add option for name=None that returns the last axes used or the new one (if none was used yet)
def axes(name: str, window: WindowSpec = None) -> Union[ReactiveAxes, plt.Axes]:
    return ReactiveAxes(widget(name, Figure, window=window).axes)


@reactive
def image_to_rgb(image: np.ndarray, is_bgr=True):
    if is_bgr and len(image.shape) == 3:
        if image.shape[2] == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        elif image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
    return image


@reactive
def show_image_mpl(name: str, image: np.ndarray, is_bgr=True, window=None, **kwargs):
    """
    :param name: Unique identifier among all widgets. If such widget doesn't exist, it will be created.
    :param image: Any image that matplotlib can plot with imshow.
    :param is_bgr: If the image has 3 components, treat them as Blue, Green, Red in this order (Red Green Blue
                    otherwise)
    :return:
    """

    return axes(name=name, window=window).imshow(image_to_rgb(image, is_bgr), **kwargs)


imshow = show_image_mpl
display_image = show_image_mpl


def clear_variables(widget_name: str):
    vars_table = widget(widget_name, VarsTable)
    vars_table.clear()


global_refs = {}


def slider(widget_name: str, var: WrapperInterface, min, max, step=1, window=None):
    w = widget(widget_name, Slider, window)
    if var is not None:
        w.var = var
    global_refs[(w, 'set_params')] = reactive(w.set_params)(min, max, step)
    return w.var


def var_in_table(widget_name: str, var_name: str, var: WrapperInterface, to_value=eval, window=None):
    assert isinstance(widget_name, str)
    var = var if var is not None else Var()  # fixme: check if there is already such a var
    vars_table = widget(widget_name, VarsTable, window)
    vars_table.insert_var(var_name, var, to_value=to_value)
    return var


def combo(widget_name: str, choices: List[Union[Any, Tuple[str, Any]]], window=None):
    w = widget(widget_name, ComboBox, window)
    global_refs[(w, 'set_choices')] = reactive(w.set_choices)(choices)
    # if widget.combo.currentIndex() < 0:
    #     widget.combo.setCurrentIndex(0)
    return widget.data_var
