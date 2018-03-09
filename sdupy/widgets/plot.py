import logging

import matplotlib
from PyQt5 import QtGui
import matplotlib.pyplot as plt
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QWidget
from math import exp, log
from matplotlib.backend_bases import key_press_handler, MouseEvent
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar

from .common.register import register_widget

matplotlib.rcParams.update({'font.size': 6})

MODIFIER_KEYS = set(['shift', 'control', 'alt'])


class Axes(QWidget):
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
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
        self.canvas.mpl_connect('key_release_event', self.on_key_release)
        self.mpl_toolbar.pan()  # we usually want to pan with mouse, since zooming is on the scroll

        self.current_modifiers = set()

        self.axes = self.figure.add_subplot(111)
        self.axes.set_adjustable('datalim')  # use whole area when keeping aspect ratio of images
        self.resizeEvent(None)

        self.setMinimumSize(200, 200)

    def on_key_press(self, event):
        if event.key in MODIFIER_KEYS:
            self.current_modifiers.add(event.key)

        # implement the default mpl key press events described at
        # http://matplotlib.org/users/navigation_toolbar.html#navigation-keyboard-shortcuts
        key_press_handler(event, self.canvas, self.mpl_toolbar)

    def on_key_release(self, event):
        if event.key in MODIFIER_KEYS and event.key in self.current_modifiers:
            self.current_modifiers.remove(event.key)

    @staticmethod
    def get_scaled_lim(lim, focus, scale_factor, mode: str):
        # Todo: use some generic method to support any scale
        if mode == 'linear':
            return [(l - focus) * scale_factor + focus for l in lim]
        elif mode == 'log':
            return [exp((log(l) - log(focus)) * scale_factor + log(focus)) for l in lim]
        else:
            logging.error("cannot zoom on '{}' scale".format(mode))

    def on_scroll(self, event: MouseEvent):
        ax = self.axes

        SCALE_PER_TICK = 1.3
        if event.button == 'up':
            scale_factor = 1 / SCALE_PER_TICK
        elif event.button == 'down':
            scale_factor = SCALE_PER_TICK
        else:
            # deal with something that should never happen
            scale_factor = 1

        if 'control' not in self.current_modifiers:
            ax.set_xlim(self.get_scaled_lim(ax.get_xlim(), event.xdata, scale_factor, ax.get_xscale()))

        if 'shift' not in self.current_modifiers:
            ax.set_ylim(self.get_scaled_lim(ax.get_ylim(), event.ydata, scale_factor, ax.get_yscale()))

        self.draw()

    def draw(self):
        self.canvas.draw()

    def resizeEvent(self, a0: QtGui.QResizeEvent):
        self.figure.tight_layout(pad=0.5)

    def dump_state(self):
        return dict(
            xlim=self.axes.get_xlim(),
            ylim=self.axes.get_ylim()
        )

    def load_state(self, state: dict):
        if 'xlim' in state:
            self.axes.set_xlim(state['xlim'])
        if 'ylim' in state:
            self.axes.set_ylim(state['ylim'])


@register_widget("matplotlib plot")
class Plot(Axes):
    pass
