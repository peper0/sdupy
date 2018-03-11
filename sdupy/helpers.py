from typing import Any, List, Tuple, Union

import cv2
import matplotlib.pyplot as plt
import numpy as np

from sdupy import gcw
from sdupy.reactive.var import RVal
from sdupy.reactive.wrapping import getter, setter
from sdupy.windows import WindowSpec, window_for_spec
from .reactive import VarBase
from .reactive.decorators import reactive, reactive_finalizable
from .widgets import ComboBox, Figure, Slider, VarsTable

kept_references = dict()  # Dict[str, Var]


def widget(name: str, factory=None, window: WindowSpec = None):
    assert isinstance(name, str)
    return window_for_spec(window).obtain_widget(name, factory)


def default_remove_plot(plot_res, axes: Figure):
    if isinstance(plot_res, list) or isinstance(plot_res, tuple):
        for i in plot_res:
            default_remove_plot(i, axes)
    else:
        plot_res.remove()
        pass


def plot_method(unbound_method, remove_func=default_remove_plot):
    @reactive_finalizable()
    def wrapped(self, *args, **kwargs):
        res = unbound_method(self, *args, **kwargs)
        figure = self.get_figure()
        assert figure is not None
        canvas = figure.canvas
        canvas.draw_idle()
        yield res

        if res and remove_func:
            remove_func(res, self.axes)
            canvas.draw_idle()

    return wrapped


class ReactiveAxes(RVal):
    def __init__(self, axes: plt.Axes):
        super().__init__()
        assert isinstance(axes, plt.Axes)
        self.provide(axes)

    plot = plot_method(plt.Axes.plot)
    errorbar = plot_method(plt.Axes.errorbar)
    scatter = plot_method(plt.Axes.scatter)
    plot_date = plot_method(plt.Axes.plot_date)
    step = plot_method(plt.Axes.step)
    loglog = plot_method(plt.Axes.loglog)
    semilogx = plot_method(plt.Axes.semilogx)
    semilogy = plot_method(plt.Axes.semilogy)
    fill_between = plot_method(plt.Axes.fill_between)
    fill_betweenx = plot_method(plt.Axes.fill_betweenx)
    bar = plot_method(plt.Axes.bar)
    barh = plot_method(plt.Axes.barh)
    stem = plot_method(plt.Axes.stem)
    eventplot = plot_method(plt.Axes.eventplot)
    pie = plot_method(plt.Axes.pie)
    stackplot = plot_method(plt.Axes.stackplot)
    broken_barh = plot_method(plt.Axes.broken_barh)
    vlines = plot_method(plt.Axes.vlines)
    hlines = plot_method(plt.Axes.hlines)
    fill = plot_method(plt.Axes.fill)

    axhline = plot_method(plt.Axes.axhline)
    axhspan = plot_method(plt.Axes.axhspan)
    axvline = plot_method(plt.Axes.axvline)
    axvspan = plot_method(plt.Axes.axvspan)

    # TODO: rest from https://matplotlib.org/api/axes_api.html#plotting

    get_xlim = getter(plt.Axes.get_xlim, ['xlim'])
    set_xlim = setter(plt.Axes.set_xlim, ['xlim'])
    get_ylim = getter(plt.Axes.get_xlim, ['xlim'])
    set_ylim = setter(plt.Axes.set_xlim, ['xlim'])

    # TODO: rest from https://matplotlib.org/api/axes_api.html#plotting


def axes(name: str, window: WindowSpec = None) -> Union[ReactiveAxes, plt.Axes]:
    return ReactiveAxes(widget(name, Figure, window=window).axes)


reactive_axes = axes


@reactive
def image_to_rgb(image: np.ndarray, is_bgr=True):
    if is_bgr and len(image.shape) == 3:
        if image.shape[2] == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        elif image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
    return image


@reactive
def display_image(widget_name: str, image: np.ndarray, use_bgr=True, main_window=None, **kwargs):
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
    vars_table = gcw().obtain_widget(widget_name, VarsTable)
    vars_table.clear()


def display_variable(widget_name: str, var_name: str, var: VarBase, to_value=None):
    assert isinstance(widget_name, str)
    vars_table = gcw().obtain_widget(widget_name, VarsTable)
    vars_table.insert_var(var_name, var, to_value=to_value)


@reactive
def input_value_from_range(widget_name: str, min, max, step) -> VarBase:
    widget = gcw().obtain_widget(widget_name, Slider)
    widget.set_params(min, max, step)
    return widget.value


@reactive
def input_value_from_list(widget_name: str, choices: List[Union[Any, Tuple[str, Any]]]) -> VarBase:
    widget = gcw().obtain_widget(widget_name, ComboBox)
    widget.set_choices(choices)
    if widget.combo.currentIndex() < 0:
        widget.combo.setCurrentIndex(0)
    return widget.data_var
