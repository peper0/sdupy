import cv2
import numpy as np
from PyQt5.QtCore import QRectF, QPointF
from pyqtgraph import ImageItem, GraphItem, PlotItem

from sdupy import reactive, reactive_finalizable


@reactive
def image_to_mpl(image: np.ndarray, is_bgr=True):
#    if image.dtype not in [np.uint8, np.uint16, np.float32]:
#        is_bgr
#        assert bad
    if len(image.shape) == 3:
        if image.shape[2] == 1:
            return image[:, :, 0]
        elif image.shape[2] == 2:
            return image[..., [0, 0, 0, 1]]
        elif image.shape[2] == 3:
            if is_bgr:
                return image[..., [2, 1, 0]]
                # return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        elif image.shape[2] == 4:
            if is_bgr:
                return image[..., [2, 1, 0, 3]]
                # return cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
        else:
            assert False, "matplotlib supports only 1, 3 or 4 channels in the image (got {})".format(image.shape[2])
    elif len(image.shape) == 2:
        pass  # ok
    else:
        assert False, "matplotlib supports only 2D or 3D images (got shape {})".format(image.shape)

    return image


@reactive_finalizable
def pg_hold_items(pg_parent, *items, zvalue=None):
    for item in items:
        if zvalue is not None:
            item.setZValue(zvalue)
        pg_parent.addItem(item)
    yield
    for item in items:
        pg_parent.removeItem(item)


@reactive
def image_to_pg(image: np.ndarray, is_bgr=True, do_flip=True):
    #FIXME: use CONFIG_OPTIONS instead of transposition
    image = image_to_mpl(image, is_bgr)
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


@reactive
def make_graph_item_pg(pos, adj, **kwargs):
    pos = np.asarray(pos)
    assert len(pos.shape) == 2 and pos.shape[1] == 2
    adj = np.array(adj, dtype=int)
    assert len(adj.shape) == 2
    item = GraphItem(pos=pos, adj=adj, **kwargs)
    item.generatePicture()  # trigger exceptions that may occur here (and would be raised inside "paint" method)
    return item


@reactive_finalizable
def make_plot_item_pg(plot_item: PlotItem, *args, **kwargs):
    item = plot_item.plot(*args, **kwargs)
    yield item
    plot_item.removeItem(item)


def set_zvalue(zvalue, *items):
    if zvalue is not None:
        for item in items:
            item.setZValue(zvalue)