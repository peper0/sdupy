import cv2
import numpy as np
from PyQt5.QtCore import QRectF, QPointF
from pyqtgraph import ImageItem

from sdupy import reactive, reactive_finalizable


@reactive
def image_to_rgb(image: np.ndarray, is_bgr=True):
    if is_bgr and len(image.shape) == 3:
        if image.shape[2] == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        elif image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
    return image


@reactive_finalizable
def pg_hold_items(pg_parent, *items):
    for item in items:
        pg_parent.addItem(item)
    yield
    for item in items:
        pg_parent.removeItem(item)


@reactive
def image_to_pg(image: np.ndarray, is_bgr=True, do_flip=True):
    #FIXME: use CONFIG_OPTIONS instead of transposition
    image = image_to_rgb(image, is_bgr)
    if do_flip:
        image = np.flip(image, axis=0)
    if len(image.shape) == 3:
        image = np.transpose(image, axes=(1, 0, 2))
        if image.shape[2] == 1:
            image = image[..., 0]
    elif len(image.shape) == 2:
        image = np.transpose(image, axes=(1, 0))
    else:
        assert False
    return image


def levels_for(image: np.ndarray):
    if image.dtype == np.uint8:
        return (0, 255)
    elif image.dtype == np.float32 or image.dtype == np.float64:
        return (0.0, 1.0)


@reactive
def make_pg_image_item(image, extent=None, **kwargs):
    image_args = kwargs
    image_args.setdefault('autoRange', False)
    image_args.setdefault('autoLevels', False)
    image_args.setdefault('axisOrder', 'row-major')
    image_args.setdefault('levels', levels_for(image))
    item = ImageItem(image, **image_args)
    if extent is not None:
        xmin, xmax, ymin, ymax = extent
        item.setRect(QRectF(QPointF(xmin, ymin), QPointF(xmax, ymax)))
    item.setAutoDownsample(True)
    return item