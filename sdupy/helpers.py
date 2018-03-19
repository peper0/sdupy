from typing import Any, List, Tuple, Union

import cv2
import matplotlib.pyplot as plt
import numpy as np

import sdupy
from .reactive import WrapperInterface
from .reactive.decorators import reactive
from .reactive.wrappers.axes import ReactiveAxes
from .widgets import ComboBox, Figure, Slider, VarsTable
from .windows import WindowSpec

kept_references = dict()  # Dict[str, Var]


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
def display_image(name: str, image: np.ndarray, use_bgr=True, window=None, **kwargs):
    """
    :param name: Unique identifier among all widgets. If such widget doesn't exist, it will be created.
    :param image: Any image that matplotlib can plot with imshow.
    :param use_bgr: If the image has 3 components, treat them as Blue, Green, Red in this order (Red Green Blue
                    otherwise)
    :return:
    """

    return axes(name=name, window=window).imshow(image_to_rgb(image, use_bgr), **kwargs)


imshow = display_image


def clear_variables(widget_name: str):
    assert isinstance(widget_name, str)
    vars_table = sdupy.window().obtain_widget(widget_name, VarsTable)
    vars_table.clear()


def display_variable(widget_name: str, var_name: str, var: WrapperInterface, to_value=None):
    assert isinstance(widget_name, str)
    vars_table = sdupy.window().obtain_widget(widget_name, VarsTable)
    vars_table.insert_var(var_name, var, to_value=to_value)


@reactive
def input_value_from_range(widget_name: str, min, max, step) -> WrapperInterface:
    widget = sdupy.window().obtain_widget(widget_name, Slider)
    widget.set_params(min, max, step)
    return widget.value


@reactive
def input_value_from_list(widget_name: str, choices: List[Union[Any, Tuple[str, Any]]]) -> WrapperInterface:
    widget = sdupy.window().obtain_widget(widget_name, ComboBox)
    widget.set_choices(choices)
    if widget.combo.currentIndex() < 0:
        widget.combo.setCurrentIndex(0)
    return widget.data_var
