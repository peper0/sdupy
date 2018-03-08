import logging
from typing import Any, List, Tuple, Union

import cv2
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes

from sdupy import gcmw
from .reactive.decorators import reactive, reactive_finalizable
from .widgets import ComboBox, Plot, Slider, VarsTable

kept_references = dict()  # Dict[str, Var]


def default_remove_plot(plot_res, axes: Axes):
    if isinstance(plot_res, list) or isinstance(plot_res, tuple):
        for i in plot_res:
            default_remove_plot(i, axes)
    else:
        plot_res.remove()
        pass


class ReactiveAxes:
    def __init__(self, axes: plt.Axes):
        self.axes = axes

    def reactive_call(self, func):
        def bound_func(*args, **kwargs):
            func(self.axes, *args, **kwargs)

        self.reactive_call_bound(bound_func)

    def __getattr__(self, func_name):
        return self.reactive_call_bound(getattr(self.axes, func_name))

    def reactive_call_bound(self, bound_func):
        @reactive_finalizable()
        def wrapped_bound_func(*args, remove_func = default_remove_plot, **kwargs):
            logging.fatal('plotting %s', kwargs)
            res = bound_func(*args, **kwargs)
            figure = self.axes.get_figure()
            assert figure is not None
            canvas = figure.canvas
            canvas.draw()
            yield res

            if res and remove_func:
                remove_func(res, self.axes)
                canvas.draw()

        return wrapped_bound_func


def reactive_axes(widget_name: str, main_window = None):
    assert isinstance(widget_name, str)
    main_window = main_window or gcmw()
    plot_widget = main_window.obtain_widget(widget_name, Plot)
    return ReactiveAxes(plot_widget.axes)


@reactive
def image_to_rgb(image: np.ndarray, is_bgr=True):
    if is_bgr and len(image.shape) == 3:
        if image.shape[2] == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        elif image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
    return image


@reactive
def display_image(widget_name: str, image: np.ndarray, use_bgr=True, main_window = None, **kwargs):
    """
    :param widget_name: Unique identifier among all widgets. If such widget doesn't exist, it will be created.
    :param image: Any image that matplotlib can plot with imshow.
    :param use_bgr: If the image has 3 components, treat them as Blue, Green, Red in this order (Red Green Blue
                    otherwise)
    :return:
    """
    kwargs.setdefault('aspect', 'equal')
    kwargs.setdefault('interpolation', 'nearest')
    return reactive_axes(widget_name=widget_name, main_window=main_window).imshow(image_to_rgb(image, use_bgr),
                                                                                  **kwargs)

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
