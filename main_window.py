import json
import logging
from typing import List, NamedTuple

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import QDockWidget, QMainWindow, QMenu, QWidget

import widgets


class WidgetInstance(NamedTuple):
    widget: QWidget
    dock_widget: QDockWidget
    factory_name: str


logging.basicConfig(level=logging.INFO)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        # self.setCentralWidget(QTextEdit())
        # noinspection PyTypeChecker
        self.setCentralWidget(None)
        self.setDockNestingEnabled(True)

        self.widgets = []  # type: List[WidgetInstance]

        self.file_menu = QMenu('&File', self)
        # self.file_menu.addAction('&Quit', self.fileQuit,
        #                          Qt.CTRL + Qt.Key_Q)
        self.menuBar().addMenu(self.file_menu)

        self.add_menu = QMenu('&Add widget', self)
        self.menuBar().addSeparator()
        self.menuBar().addMenu(self.add_menu)

        for factory_name in widgets.factories.keys():
            self.add_factory_to_gui(factory_name)

        try:
            with open("state.json") as f:
                self.load_state(json.load(f))
        except Exception:
            logging.exception("exception during reading state file; ignoring")

    def add_factory_to_gui(self, factory_name):
        def add_widget():
            self.add_widget_from_factory(factory_name)

        self.add_menu.addAction(factory_name, add_widget)

    def add_widget_from_factory(self, factory_name, title=None):
        widget = widgets.factories[factory_name](parent=self)
        self.add_widget(widget, factory_name, title)
        return widget

    def add_widget(self, widget, factory_name, title=None):
        def generate_names(base):
            yield base
            for i in range(1, 1000):
                yield base + ' ' + str(i)

        for title in generate_names(title or factory_name):
            if all((title != i.dock_widget.windowTitle() for i in self.widgets)):
                break

        docked = QDockWidget(title)
        docked.setObjectName(title)
        docked.setWidget(widget)
        self.widgets.append(WidgetInstance(widget=widget, dock_widget=docked, factory_name=factory_name))
        self.addDockWidget(Qt.RightDockWidgetArea, docked)

    def closeEvent(self, a0: QCloseEvent):
        with open("state.json", 'w') as f:
            json.dump(self.dump_state(), f)

    def dump_state(self):
        widgets_state = []
        for i in self.widgets:
            try:
                widgets_state.append((i.widget.dump_state() if hasattr(i.widget, "dump_state") else None,
                                      i.factory_name, i.dock_widget.windowTitle()))
            except Exception:
                logging.exception("ignoring exception during serialization of {}".format(i.dock_widget.windowTitle()))

        return dict(
            geometry=bytes(self.saveGeometry()).hex(),
            state=bytes(self.saveState()).hex(),
            widgets=widgets_state
        )

    def load_state(self, state: dict):
        if 'geometry' in state:
            self.restoreGeometry(bytes.fromhex(state['geometry']))
        if 'widgets' in state:
            for widget_state, factory_name, title in state['widgets']:
                try:
                    logging.info("restoring state of '{}'".format(title))
                    widget = self.add_widget_from_factory(factory_name, title)
                    if widget_state:
                        widget.load_state(widget_state)
                except Exception:
                    logging.exception(
                        "ignoring exception during restoring widget from factory '{}".format(factory_name))
        if 'state' in state:
            self.restoreState(bytes.fromhex(state['state']))
