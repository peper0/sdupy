from PyQt5.QtWidgets import QCheckBox, QVBoxLayout, QWidget

from .common.qt_property_var import QtPropertyVar
from .common.register import register_widget, registered_factories
from .figure import Figure
from .pyqtgraph import PyQtGraphPlot, PyQtGraphViewBox
from .slider import Slider
# from .console import make_console
from .tables import PandasTable, VarsTable, ArrayTable
from .combo import ComboBox


@register_widget("checkbox")
class CheckBox(QCheckBox):
    def __init__(self, parent):
        super().__init__(parent)
        self.var = QtPropertyVar(self, 'checked')

    def dump_state(self):
        return dict(
            checked=self.isChecked()
        )

    def load_state(self, state: dict):
        if 'current_text' in state:
            self.setChecked(state['checked'])
