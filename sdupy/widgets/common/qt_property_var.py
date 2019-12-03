import pyqtgraph as pg
from PyQt5.QtCore import QObject

from sdupy.pyreactive.common import Wrapped
from sdupy.pyreactive.forwarder import ConstForwarders, MutatingForwarders
from sdupy.pyreactive.notifier import Notifier, ScopedName


class QtSignaledVar(Wrapped, ConstForwarders, MutatingForwarders):
    def __init__(self, signal):
        super().__init__()
        self._notifier = Notifier()
        signal.connect(self._prop_changed)

    def _prop_changed(self):
        self._notifier.notify_observers()

    def set(self, value):
        self.obj.setProperty(self.prop_name, value)

    def get(self):
        res= self.obj.property(self.prop_name)
        return res

    def _target(self):
        return self

    @property
    def __notifier__(self):
        return self._notifier

    @property
    def __inner__(self):
        return self.get()

    @__inner__.setter
    def __inner__(self, value):
        return self.set(value)


class QtPropertyVar(QtSignaledVar):
    def __init__(self, obj: QObject, prop_name: str):
        self.obj = obj
        self.prop_name = prop_name
        obj_meta = obj.staticMetaObject
        prop_meta = obj_meta.property(obj_meta.indexOfProperty(prop_name))
        notify_signal_meta = prop_meta.notifySignal()
        assert notify_signal_meta, "property '{}' has no notifier".format(prop_name)
        notify_signal_name = bytes(notify_signal_meta.name()).decode('utf8')
        assert notify_signal_name, "property '{}' notifier has no name?!".format(prop_name)
        notify_signal = getattr(obj, notify_signal_name)
        with ScopedName(obj.objectName()+'.'+prop_name):
            super().__init__(notify_signal)

    def set(self, value):
        self.obj.setProperty(self.prop_name, value)

    def get(self):
        return self.obj.property(self.prop_name)


class QtPropertyVar2(QtSignaledVar):
    def __init__(self, notify_signal, getter, setter=None):
        self.setter = setter
        self.getter = getter
        super().__init__(notify_signal)

    def set(self, value):
        self.setter(value)

    def get(self):
        return self.getter()


class PgParamVar(QtSignaledVar):
    def __init__(self, line: pg.InfiniteLine):
        super().__init__(line.sigPositionChangeFinished)
        self.param = line

    def set(self, value):
        self.param.setValue(value)

    def get(self):
        return self.param.value()