import os

import cv2
import matplotlib.pyplot as plt

from . import studioapp
from .reactive.reactive import reactive_finalizable
from .widgets import Plot


@reactive_finalizable()
def show_image(widget_name: str, image, use_bgr=True):
    assert isinstance(widget_name, str)
    plot = studioapp.default_main_window.obtain_widget(widget_name, Plot)
    if use_bgr and len(image.shape) == 3 and image.shape[2] == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    img = plot.axes.imshow(image)  # type: plt.image.AxesImage
    plot.draw()
    yield
    os.write(1, b"removing\n")
    img.remove()
