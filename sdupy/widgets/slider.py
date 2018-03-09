from math import ceil, log10

from PyQt5 import QtCore
from PyQt5.QtWidgets import QDoubleSpinBox, QHBoxLayout, QScrollBar, QWidget

from sdupy.reactive import Var, reactive
from sdupy.widgets.common.qt_property_var import QtPropertyVar
from sdupy.widgets.common.register import register_widget


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
        self.value = Var()
        self.refs = [self._set_vals((val,), val)
                     for val in [self._spin_val, self._slider_val, self.value]]
        self._step = None
        self._min = None
        self._max = None

    def _uses_integer(self):
        return isinstance(self._slider_mult, int)

    @reactive
    def _set_vals(self, source_tup, value):
        source, = source_tup
        if source is self._slider_val:
            if self._uses_integer:
                value /= self._slider_mult
            else:
                value /= self._slider_mult
        if self._uses_integer():
            value = round(value)
        if source is not self._slider_val: self._slider_val.set(value * self._slider_mult)
        if source is not self._spin_val: self._spin_val.set(value)
        if source is not self.value: self.value.set(value)

    def set_params(self, min, max, step=1):
        self._step = step
        self._min = min
        self._max = max

        if isinstance(min, float) or isinstance(max, float) or isinstance(step, float):
            self._slider_mult = 1.0 / step
            self.spin_box.setDecimals(ceil(-log10(step)))
        else:
            self._slider_mult = 1
            self.spin_box.setDecimals(0)
        self.slider.setRange(int(min * self._slider_mult), int(max * self._slider_mult))
        self.slider.setSingleStep(int(step * self._slider_mult))
        self.spin_box.setRange(min, max)
        self.spin_box.setSingleStep(step)

        if self.value.get() > max:
            self.value.set(max)
        elif self.value.get() < min:
            self.value.set(min)

    def dump_state(self):
        return dict(
            min=self._min,
            max=self._max,
            step=self._step,
            value=self.value.get()
        )

    def load_state(self, state: dict):
        self.set_params(state['min'], state['max'], state['step'])
        self.value.set(state['value'])
