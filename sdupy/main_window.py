import json
import logging
import os
from typing import Dict, NamedTuple

import appdirs
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import QDockWidget, QMainWindow, QMenu, QWidget

from sdupy.utils import ignore_errors
from . import widgets
from .widgets.common.register import FactoryDesc


class WidgetInstance(NamedTuple):
    widget: QWidget
    name: str  # used to programatically identify widget instance (in configs, in function calls)
    dock_widget: QDockWidget
    factory_name: str


class MainWindow(QMainWindow):
    def __init__(self, parent=None, title=None, app_id=None, default_state_dir=None):
        super().__init__(parent)
        # self.setCentralWidget(QTextEdit())
        # noinspection PyTypeChecker
        self._last_dock = None
        self.app_id = app_id
        self.setCentralWidget(None)
        self.setDockNestingEnabled(True)
        self.setWindowTitle(title)

        self.widgets = {}  # type: Dict[str, WidgetInstance]

        self.file_menu = QMenu('&App', self)
        self.save_layout_action = self.file_menu.addAction('&Save state', ignore_errors(self.save_state_to_file),
                                                           Qt.CTRL + Qt.Key_S)
        self.save_layout_action.setEnabled(bool(self.app_id))
        self.save_layout_def_action = self.file_menu.addAction('Save sate as &default',
                                                               lambda: self.save_state_to_file(save_as_default=True))
        self.save_layout_def_action.setEnabled(bool(self.app_id))
        self.menuBar().addMenu(self.file_menu)

        # self.add_menu = QMenu('&Add widget', self)
        # self.menuBar().addSeparator()
        # self.menuBar().addMenu(self.add_menu)

        self.remove_menu = QMenu('&Remove widget', self)
        self.menuBar().addMenu(self.remove_menu)

        self.close_callback = None

        self.resize(400, 400)  # workaround some bugs

        for factory_desc in widgets.registered_factories.values():
            self.add_factory_to_gui(factory_desc)

        self.user_state_path = os.path.join(appdirs.user_data_dir('sdupy', 'peper0'),
                                            "{}.state.json".format(self.app_id)) if app_id else None
        self.default_state_path = os.path.join(default_state_dir, "{}.state.json".format(self.app_id)) \
            if app_id and default_state_dir else None

        self.load_state_std()

    def load_state_std(self):
        """
        State is loaded at construction time but some controls cannot restore themselves correctly before in-app
        initialization (e.g. parameter trees). It's good therefore to call this function after initializing the
        application.
        """
        state_path = (self.user_state_path
                      if self.user_state_path and os.path.exists(self.user_state_path)
                      else self.default_state_path)
        if state_path:
            try:
                logging.info("loading application state from '{}'".format(state_path))
                with open(state_path) as f:
                    self.load_state(json.load(f))
            except Exception:
                logging.exception("exception during reading state file; ignoring")

    def add_factory_to_gui(self, factory_desc: FactoryDesc):
        def add_widget():
            self.add_widget_from_factory(factory_desc,
                                         self.generate_widget_name(factory_desc.name),
                                         self.generate_widget_title(factory_desc.pretty_name))

        # self.add_menu.addAction(factory_desc.pretty_name, add_widget)

    def add_widget_from_factory(self, factory_desc: FactoryDesc, widget_name, title):
        docked = QDockWidget(title)
        widget = factory_desc.factory(parent=docked, name=widget_name)
        # self.add_widget(widget, factory_desc.name, widget_name, title)
        docked.setObjectName(title)
        docked.setWidget(widget)
        assert widget_name not in self.widgets
        self.widgets[widget_name] = WidgetInstance(widget=widget, name=widget_name, dock_widget=docked,
                                                   factory_name=factory_desc.name)
        self.addDockWidget(Qt.RightDockWidgetArea, docked)
        # FIXME: better automatic layout
        # #        good_docks = [w.dock_widget for w in self.widgets.values() if w.dock_widget != docked]
        # #        if good_docks:
        #         if self._last_dock is not None:
        #             self.tabifyDockWidget(docked, self._last_dock)
        #
        #         self._last_dock = docked

        action_listref = []

        def remove_widget():
            self.remove_widget(widget_name)
            self.remove_menu.removeAction(action_listref[0])

        action_listref.append(self.remove_menu.addAction(widget_name, remove_widget))

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

    def remove_widget(self, widget_name):
        self.removeDockWidget(self.widgets[widget_name].dock_widget)
        del self.widgets[widget_name]

    def obtain_widget_instance(self, name, factory_or_name):
        if name not in self.widgets:
            assert factory_or_name is not None, f"object {name} not found and no factory provided"
            if isinstance(factory_or_name, str):
                factory_desc = widgets.registered_factories[factory_or_name]
            else:
                factory_desc = widgets.registered_factories[factory_or_name.__name__]
                # factory_descs = [fd for fd in widgets.registered_factories.values() if fd.factory == factory_or_name]
                # if not factory_descs:
                #     raise Exception("not existent factory: {} ('{}'); known factories are: {})".format(
                #         factory_or_name, factory_or_name.__name__,
                #         [fd.factory for fd in widgets.registered_factories.values()]))
                # factory_desc = factory_descs[0]
            self.add_widget_from_factory(factory_desc, widget_name=name, title=name)

        return self.widgets[name]

    def obtain_widget(self, name, factory_or_name):
        wi = self.obtain_widget_instance(name, factory_or_name)
        return wi.widget, wi.dock_widget

    def closeEvent(self, a0: QCloseEvent):
        self.save_state_to_file()
        if self.close_callback:
            self.close_callback()

    def save_state_to_file(self, save_as_default=False):
        state_path = self.user_state_path if not save_as_default else self.default_state_path
        if state_path:
            state_as_json = json.dumps(
                self.dump_state())  # we do it before overwritting a file since there may be error
            logging.info("Saving application state to '{}'".format(state_path))
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            with open(state_path, 'w') as f:
                f.write(state_as_json)

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
                    logging.debug("restoring state of '{}'".format(title))

                    if widget_name in self.widgets:
                        widget = self.widgets[widget_name].widget
                    else:
                        widget = self.add_widget_from_factory(widgets.registered_factories[factory_name], widget_name,
                                                              title)
                    if widget_state:
                        widget.load_state(widget_state)
                except Exception:
                    logging.exception(
                        "ignoring exception during restoring widget from factory '{}".format(factory_name))
        if 'state' in state:
            self.restoreState(bytes.fromhex(state['state']))
