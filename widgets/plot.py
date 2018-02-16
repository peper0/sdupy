import matplotlib.pyplot as plt
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QWidget
from matplotlib.backend_bases import key_press_handler
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar

from .common.register import register_widget


@register_widget("matplotlib plot")
class Plot(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.figure = plt.figure()
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setParent(self)
        self.canvas.setFocusPolicy(Qt.StrongFocus)
        self.canvas.setFocus()
        self.layout.addWidget(self.canvas)

        self.mpl_toolbar = NavigationToolbar(self.canvas, self)
        self.layout.addWidget(self.mpl_toolbar)
        self.canvas.mpl_connect('key_press_event', self.on_key_press)

        self.axes = self.figure.add_subplot(111)
        self.canvas.draw()

        # self.tree = QTreeView()
        # self.tree.setModel(DataTreeModel(self.studio, self))
        # self.layout.addWidget(self.tree)

    def on_key_press(self, event):
        print('you pressed', event.key)
        # implement the default mpl key press events described at
        # http://matplotlib.org/users/navigation_toolbar.html#navigation-keyboard-shortcuts
        key_press_handler(event, self.canvas, self.mpl_toolbar)

    def draw(self):
        self.canvas.draw()
