import json
import logging
from typing import Dict, NamedTuple

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import QDockWidget, QMainWindow, QMenu, QWidget

from . import widgets
from .widgets.common.register import FactoryDesc


class WidgetInstance(NamedTuple):
    widget: QWidget
    name: str  # used to programatically identify widget instance (in configs, in function calls)
    dock_widget: QDockWidget
    factory_name: str


logging.basicConfig(level=logging.INFO)


class MainWindow(QMainWindow):
    def __init__(self, parent=None, state_name=''):
        super().__init__(parent)
        # self.setCentralWidget(QTextEdit())
        # noinspection PyTypeChecker
        self.state_name = state_name
        self.setCentralWidget(None)
        self.setDockNestingEnabled(True)

        self.widgets = {}  # type: Dict[str, WidgetInstance]

        self.file_menu = QMenu('&File', self)
        self.file_menu.addAction('&Save layout', self.save_state_action, Qt.CTRL + Qt.Key_S)
        self.menuBar().addMenu(self.file_menu)

        self.add_menu = QMenu('&Add widget', self)
        self.menuBar().addSeparator()
        self.menuBar().addMenu(self.add_menu)

        for factory_desc in widgets.registered_factories.values():
            self.add_factory_to_gui(factory_desc)

        try:
            with open("{}.state.json".format(state_name)) as f:
                self.load_state(json.load(f))
        except Exception:
            logging.exception("exception during reading state file; ignoring")

    def add_factory_to_gui(self, factory_desc: FactoryDesc):
        def add_widget():
            self.add_widget_from_factory(factory_desc,
                                         self.generate_widget_name(factory_desc.name),
                                         self.generate_widget_title(factory_desc.pretty_name))

        self.add_menu.addAction(factory_desc.pretty_name, add_widget)

    def add_widget_from_factory(self, factory_desc: FactoryDesc, widget_name, title):
        widget = factory_desc.factory(parent=self)
        self.add_widget(widget, factory_desc.name, widget_name, title)
        return widget

    def generate_widget_name(self, base):
        i = 0
        while True:
            name = base + ' ' + str(i)
            if name not in self.widgets.keys():
                return name

    def generate_widget_title(self, base):
        def generate_titles():
            yield base
            for i in range(1, 10000):
                yield base + ' ' + str(i)

        for title in generate_titles():
            if all((title != i.dock_widget.windowTitle() for i in self.widgets.values())):
                return title

    def add_widget(self, widget: QWidget, factory_name, widget_name, title):
        docked = QDockWidget(title)
        docked.setObjectName(title)
        docked.setWidget(widget)
        assert widget_name not in self.widgets
        self.widgets[widget_name] = WidgetInstance(widget=widget, name=widget_name, dock_widget=docked,
                                                   factory_name=factory_name)
        self.addDockWidget(Qt.RightDockWidgetArea, docked)

    def obtain_widget(self, name, factory_or_name):
        if name not in self.widgets:
            if isinstance(factory_or_name, str):
                factory_desc = widgets.registered_factories[factory_or_name]
            else:
                factory_desc = [fd for fd in widgets.registered_factories.values() if fd.factory == factory_or_name][0]
            self.add_widget_from_factory(factory_desc, widget_name=name, title=name)

        return self.widgets[name].widget

    def closeEvent(self, a0: QCloseEvent):
        self.save_state_action()

    def save_state_action(self):
        with open("{}.state.json".format(self.state_name), 'w') as f:
            json.dump(self.dump_state(), f)

    def dump_state(self):
        widgets_state = []
        for i in self.widgets.values():
            try:
                widgets_state.append((
                    i.name,
                    i.factory_name,
                    i.dock_widget.windowTitle(),
                    i.widget.dump_state() if hasattr(i.widget, "dump_state") else None))
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
            for widget_name, factory_name, title, widget_state in state['widgets']:
                try:
                    logging.info("restoring state of '{}'".format(title))
                    widget = self.add_widget_from_factory(widgets.registered_factories[factory_name], widget_name,
                                                          title)
                    if widget_state:
                        widget.load_state(widget_state)
                except Exception:
                    logging.exception(
                        "ignoring exception during restoring widget from factory '{}".format(factory_name))
        if 'state' in state:
            self.restoreState(bytes.fromhex(state['state']))
