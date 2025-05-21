from numbers import Number, Integral
from typing import Mapping, Sequence
from builtins import isinstance
from collections import OrderedDict

import numpy as np
from PyQt5.QtCore import QRectF, QPointF
from pyqtgraph import ImageItem, GraphItem, PlotItem, ScatterPlotWidget

from sdupy.pyreactive import reactive, reactive_finalizable


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


@reactive
def pg_hold_items_unroll(pg_parent, items, zvalue=None):
    if items is None:
        items = []
    return pg_hold_items(pg_parent, *items, zvalue=zvalue)


@reactive_finalizable
def pg_hold_items(pg_parent, *items, zvalue=None):
    vb = pg_parent.vb if hasattr(pg_parent, 'vb') else pg_parent
    ar = vb.autoRangeEnabled()  # it slow downs when inserting many objects
    vb.disableAutoRange()

    for item in items:
        if item is not None:
            if zvalue is not None:
                assert item is not None
                item.setZValue(zvalue)
            pg_parent.addItem(item)
    vb.enableAutoRange(x=ar[0], y=ar[0])
    yield
    ar = vb.autoRangeEnabled()  # it slow downs when inserting many objects
    vb.disableAutoRange()
    for item in items:
        if item is not None:
            pg_parent.removeItem(item)
    vb.enableAutoRange(x=ar[0], y=ar[0])


@reactive
def image_to_pg(image: np.ndarray, is_bgr=True, do_flip=True):
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
    if image is None:
        return None
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
    adj = np.array(adj, dtype=int) if len(adj) != 0 else np.zeros((0, 2), dtype=int)
    item = GraphItem(pos=pos, adj=adj, **kwargs)
    item.generatePicture()  # trigger exceptions that may occur here (and would be raised inside "paint" method)
    return item


@reactive_finalizable
def make_plot_item_pg(plot_item: PlotItem, *args, **kwargs):
    item = plot_item.plot(*args, **kwargs)
    yield item
    plot_item.removeItem(item)


def flatten_dicts(record, prefix=''):
    for k, v in record.items():
        if isinstance(v, Mapping):
            yield from flatten_dicts(v, prefix+k+'.')
        else:
            yield prefix+k, v


@reactive
def set_scatter_data_pg(widget: ScatterPlotWidget, data):
    def field_flags(name, ftype, values):
        if not issubclass(ftype, Number):
            return dict(mode='enum', values=list(values))
        return dict(values=list(set(values)))

    if isinstance(data, Sequence) and len(data) > 0 and isinstance(data[0], Mapping):
        ftypes = OrderedDict()
        fvalues = OrderedDict()

        def to_acceptable_value(v):
            if isinstance(v, Number):
                return v
            else:
                return str(v)

        for record in data:
            for k, v in flatten_dicts(record):
                acc_val = to_acceptable_value(v)
                ftypes[k] = type(acc_val)
                fvalues.setdefault(k, set()).add(acc_val)

        def ftype_to_numpy(ftype):
            if issubclass(ftype, str):
                return 'U1024'
            return ftype

        dtype = [(name, ftype_to_numpy(ftype)) for name, ftype in ftypes.items()]
        data_ar = np.empty(len(data), dtype=dtype)
        for i, record in enumerate(data):
            for k, v in flatten_dicts(record):
                data_ar[i][k] = to_acceptable_value(v)

        widget.setFields([(name, field_flags(name, ftypes[name], fvalues[name]))
                          for name in ftypes])

    elif isinstance(data, np.ndarray):
        widget.setFields([(name, field_flags(name, data.dtype.fields[name][0].type, data[name]))
                          for name in data.dtype.names])
        data_ar = data

    else:
        raise Exception("data type not supported, you may want to add the support here")

    widget.setData(data_ar)


def set_zvalue(zvalue, *items):
    if zvalue is not None:
        for item in items:
            item.setZValue(zvalue)


