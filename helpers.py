import os

import cv2
import matplotlib.pyplot as plt
import numpy as np

from sdupy.reactive import VarBase
from sdupy.studioapp import gcmw
from sdupy.widgets import Slider
from . import studioapp
from .reactive.reactive import reactive_finalizable
from .reactive import Var
from .widgets import Plot

kept_references = dict()  # Dict[str, Var]


@reactive_finalizable()
def imshow(widget_name: str, image: np.ndarray, use_bgr=True, **kwargs):
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
        if use_bgr and len(image.shape) == 3 and image.shape[2] == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        axes_image = plot.axes.imshow(image, **kwargs)  # type: plt.image.AxesImage
    plot.draw()
    yield
    os.write(1, b"removing\n")
    if axes_image is not None:
        axes_image.remove()


def input_value_from_range(widget_name: str, min, max, step) -> VarBase:
    widget = studioapp.default_main_window.obtain_widget(widget_name, Slider)
    widget.set_params(min, max, step)
    return widget.var


def input_value_from_list(widget_name: str, allowed_values) -> VarBase:
    # TODO: make some combobox
    raise NotImplemented
