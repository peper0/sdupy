from PyQt5 import QtCore
from PyQt5.QtWidgets import QScrollBar, QVBoxLayout, QWidget

from sdupy.widgets.common.qt_property_var import QtPropertyVar
from sdupy.widgets.common.register import register_widget


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
