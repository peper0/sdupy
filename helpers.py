import os
from typing import Any, List, Tuple, Union

import cv2
import matplotlib.pyplot as plt
import numpy as np

from sdupy.reactive import VarBase
from sdupy.studioapp import gcmw
from sdupy.widgets import ComboBox, Slider, VarsTable
from .reactive.reactive import reactive_finalizable, reactive
from .widgets import Plot

kept_references = dict()  # Dict[str, Var]


@reactive_finalizable()
def display_image(widget_name: str, image: np.ndarray, use_bgr=True, **kwargs):
    """
    :param widget_name: Unique identifier among all widgets. If such widget doesn't exist, it will be created.
    :param image: Any image that matplotlib can plot with imshow.
    :param use_bgr: If the image has 3 components, treat them as Blue, Green, Red in this order (Red Green Blue
                    otherwise)
    :param keep: Keep the image even when no reference to the returned object is kept. Only the last one is kept for
                 each widget.
    :return:
    """
    assert isinstance(widget_name, str)
    plot = gcmw().obtain_widget(widget_name, Plot)
    axes_image = None

    if image is not None:
        kwargs.setdefault('aspect', 'equal')
        kwargs.setdefault('interpolation', 'nearest')
        if use_bgr and len(image.shape) == 3:
            if image.shape[2] == 3:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            elif image.shape[2] == 4:
                image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
        axes_image = plot.axes.imshow(image, **kwargs)  # type: plt.image.AxesImage
    plot.draw()
    yield
    os.write(1, b"removing\n")
    if axes_image is not None:
        axes_image.remove()
        plot.draw()


imshow = display_image


def clear_variables(widget_name: str):
    assert isinstance(widget_name, str)
    vars_table = gcmw().obtain_widget(widget_name, VarsTable)
    vars_table.clear()


def display_variable(widget_name: str, var_name: str, var: VarBase, to_value=None):
    assert isinstance(widget_name, str)
    vars_table = gcmw().obtain_widget(widget_name, VarsTable)
    vars_table.insert_var(var_name, var, to_value=to_value)


@reactive
def input_value_from_range(widget_name: str, min, max, step) -> VarBase:
    widget = gcmw().obtain_widget(widget_name, Slider)
    widget.set_params(min, max, step)
    return widget.value


@reactive
def input_value_from_list(widget_name: str, choices: List[Union[Any, Tuple[str, Any]]]) -> VarBase:
    widget = gcmw().obtain_widget(widget_name, ComboBox)
    widget.set_choices(choices)
    if widget.combo.currentIndex() < 0:
        widget.combo.setCurrentIndex(0)
    return widget.data_var


def func():
    print(333)
    a=4
    print(a)
