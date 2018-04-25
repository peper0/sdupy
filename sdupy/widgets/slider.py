from math import ceil, log10

from PyQt5 import QtCore
from PyQt5.QtWidgets import QDoubleSpinBox, QHBoxLayout, QScrollBar, QWidget

from sdupy.pyreactive import Var, reactive
from sdupy.pyreactive.common import unwrap_def, unwrap
from sdupy.pyreactive.var import NotInitializedError, volatile
from sdupy.widgets.common.qt_property_var import QtPropertyVar
from sdupy.widgets.common.register import register_widget


def set_if_inequal(var_to_set, new_value):
    try:
        print("{} is {}".format(repr(var_to_set), var_to_set.__inner__))
        if var_to_set.__inner__ == new_value:
            return
    except NotInitializedError:
        pass
    print("setting {} to {}".format(repr(var_to_set), new_value))
    var_to_set.__inner__ = new_value



@register_widget("slider")
class Slider(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.setLayout(self.layout)

        self.slider = QScrollBar(self)
        self.spin_box = QDoubleSpinBox(self)
        self.spin_box.setMaximumWidth(70)
        self.layout.addWidget(self.slider)
        self.layout.addWidget(self.spin_box)

        self.slider.setOrientation(QtCore.Qt.Horizontal)
        self.slider.setPageStep(1)

        self._slider_mult = 1

        self._spin_val = QtPropertyVar(self.spin_box, 'value')
        self._slider_val = QtPropertyVar(self.slider, 'value')

        self._var = None
        self.set_from_value = None

        self._step = None
        self._min = None
        self._max = None

        self.var = Var()

    def _uses_integer(self):
        return isinstance(self._slider_mult, int)

    @reactive
    def _set_all_to(self, value):
        print("set all to ", value)
        if self._uses_integer():
            value = int(round(value))
        set_if_inequal(self._slider_val, value * self._slider_mult)
        set_if_inequal(self._spin_val, value)
        set_if_inequal(self._var, value)

    @property
    def var(self):
        return self._var

    @var.setter
    def var(self, var):
        self._var = var if var is not None else Var()
        self.set_from_value = volatile(self._set_all_to(self._var))

    def set_params(self, min, max, step=1):
        self._step = step
        self._min = min
        self._max = max

        if isinstance(min, float) or isinstance(max, float) or isinstance(step, float):
            self._slider_mult = 1.0 / step
            self.spin_box.setDecimals(int(ceil(-log10(step))))
        else:
            self._slider_mult = 1
            self.spin_box.setDecimals(0)
        self.slider.setRange(int(min * self._slider_mult), int(max * self._slider_mult))
        self.slider.setSingleStep(int(step * self._slider_mult))
        self.spin_box.setRange(min, max)
        self.spin_box.setSingleStep(step)
        self.refs = [
            volatile(self._set_all_to(self._spin_val)),
            volatile(self._set_all_to(self._slider_val / self._slider_mult))
        ]


        val = unwrap_def(self._var, None)
        if val is not None:
            if val > max:
                self._var.set(max)
            elif val < min:
                self._var.set(min)

    def dump_state(self):
        return dict(
            min=self._min,
            max=self._max,
            step=self._step,
            value=unwrap(self._var)
        )

    def load_state(self, state: dict):
        self.set_params(state['min'], state['max'], state['step'])
        self._var.set(state['value'])
