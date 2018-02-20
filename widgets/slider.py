from math import ceil, log10

from PyQt5 import QtCore
from PyQt5.QtWidgets import QDoubleSpinBox, QHBoxLayout, QScrollBar, QWidget

from sdupy.reactive import Var, reactive
from sdupy.reactive.var import myprint
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

        self._slider_mult = 1

        self._spin_val = QtPropertyVar(self.spin_box, 'value')
        self._slider_val = QtPropertyVar(self.slider, 'value')
        self.value = Var()
        self.refs = [self._set_vals((val,), val)
                     for val in [self._spin_val, self._slider_val, self.value]]

    def _uses_integer(self):
        return isinstance(self._slider_mult, int)

    @reactive
    def _set_vals(self, source_tup, value):
        source, = source_tup
        myprint(source, value)
        if source == self._slider_val:
            if self._uses_integer:
                value /= self._slider_mult
            else:
                value /= self._slider_mult
        if self._uses_integer():
            value = round(value)
        if source != self._slider_val: self._slider_val.set(value * self._slider_mult)
        if source != self._spin_val: self._spin_val.set(value)
        if source != self.value: self.value.set(value)

    def set_params(self, min, max, step=1, page_step=None):
        if isinstance(min, float) or isinstance(max, float) or isinstance(step, float):
            self._slider_mult = 1.0 / step
            self.spin_box.setDecimals(ceil(-log10(step)))
        else:
            self._slider_mult = 1
            self.spin_box.setDecimals(0)
        myprint("uses int", self._uses_integer())
        self.slider.setRange(int(min * self._slider_mult), int(max * self._slider_mult))
        self.slider.setSingleStep(int(step * self._slider_mult))
        self.spin_box.setRange(min, max)
        self.spin_box.setSingleStep(step)
