from PyQt5 import QtCore
from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QScrollBar, QVBoxLayout, QWidget

from sdupy.reactive import VarBase
from sdupy.widgets.common.register import register_widget


def connect_to_notifier(obj, prop_name, callback):
    meta = obj.meta
    notify_signal_name = bytes(meta.property(meta.indexOfProperty(prop_name)).notifySignal().name()).decode('utf8')
    notify_signal = getattr(obj, notify_signal_name)
    notify_signal.connect(callback)


class QtPropertyVar(VarBase):
    def __init__(self, obj: QObject, prop_name: str):
        super().__init__()
        self.obj = obj
        self.prop_name = prop_name
        obj_meta = obj.staticMetaObject
        prop_meta = obj_meta.property(obj_meta.indexOfProperty(prop_name))
        notify_signal_name = bytes(prop_meta.notifySignal().name()).decode('utf8')
        notify_signal = getattr(obj, notify_signal_name)
        notify_signal.connect(self._prop_changed)

    def _prop_changed(self):
        self.notify_observers()

    def set(self, value):
        self.obj.setProperty(self.prop_name, value)

    def get(self):
        return self.obj.property(self.prop_name)


@register_widget("slider")
class Slider(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.slider = QScrollBar(self)
        self.layout.addWidget(self.slider)

        self.slider.setOrientation(QtCore.Qt.Horizontal)

        self.var = QtPropertyVar(self.slider, 'value')
        self.multiplier = 1

    def set_params(self, min, max, step=1, page_step=None):
        if isinstance(min, float) or isinstance(max, float) or isinstance(step, float):
            self.multiplier = 1.0 / step
        else:
            self.multiplier = 1
        self.slider.setRange(int(min * self.multiplier), int(max * self.multiplier))
        self.slider.setSingleStep(int(step * self.multiplier))
