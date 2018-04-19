from typing import List, Union, Any, Tuple

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QComboBox

from ..pyreactive import reactive
from . import register_widget, QtPropertyVar


@register_widget("selector")
class ComboBox(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.combo = QComboBox(self)
        self.layout.addWidget(self.combo)

        self.title_var = QtPropertyVar(self.combo, 'currentText')
        self.index_var = QtPropertyVar(self.combo, 'currentIndex')
        self.data_var = reactive()(lambda x: self.combo.currentData())(self.index_var)

    def set_choices(self, choices: List[Union[Any, Tuple[str, Any]]]):
        self.combo.clear()
        for td in choices:
            if isinstance(td, tuple) and len(td) == 2:
                title, data = td
            else:
                data = td
                title = str(td)
            self.combo.addItem(title, data)

    def dump_state(self):
        return dict(
            current_text=self.combo.currentText()
        )

    def load_state(self, state: dict):
        if 'current_text' in state:
            self.combo.setCurrentText(state['current_text'])