import logging
from contextlib import suppress
from typing import Sequence

from PyQt5.QtWidgets import QWidget
from pyqtgraph.parametertree import ParameterTree, Parameter

from sdupy.pyreactive import Wrapped, is_wrapper
from sdupy.pyreactive.notifier import ScopedName
from sdupy.pyreactive.refresher import logger as notify_logger
from sdupy.pyreactive.var import Proxy
from sdupy.utils import trace


def paramtree_get_root_parameters(pt: ParameterTree) -> Sequence[Parameter]:
    root = pt.invisibleRootItem()
    return [root.child(i).param for i in range(root.childCount())]


def paramtree_dump_params(param_tree: ParameterTree) -> dict:
    import pickle
    state = {}
    all_root_params = paramtree_get_root_parameters(param_tree)
    for i in all_root_params:
        try:
            ss = i.saveState('user')
            state[i.name()] = pickle.dumps(ss).hex()
        except:
            logging.exception("ignoring error when saving {}".format(i.name()))
    return state


def paramtree_load_params(param_tree: ParameterTree, state: dict):
    import pickle
    all_root_params = paramtree_get_root_parameters(param_tree)
    for i in all_root_params:
        if i.name() in state:
            i.restoreState(pickle.loads(bytes.fromhex(state[i.name()])), addChildren=False, removeChildren=False)


class TriggerIfVisible(Proxy):
    def __init__(self, other_var: Wrapped, widget: QWidget):
        with ScopedName('trig_if_vis'):
            super().__init__(other_var)
        self.widget = widget
        self._notifier.notify_func = self._trigger
        self._other_var.__notifier__.add_observer(self._notifier)
        self.widget.visibilityChanged.connect(self._trigger)

    @trace
    def _is_visible(self):
        if hasattr(self.widget, 'visibleRegion2'):
            return bool(self.widget.visibleRegion2().rects())
        else:
            return bool(self.widget.visibleRegion().rects())

    def _trigger(self):
        if self._is_visible():
            with suppress(Exception):
                notify_logger.info('widget {} is visible; updating {}'.format(self.widget.objectName(),
                                                                              self._other_var.__notifier__.name))
                self._other_var.__inner__  # trigger run even if the result is not used
        return True


def trigger_if_visible(var_or_val, widget):
    if is_wrapper(var_or_val):
        return TriggerIfVisible(var_or_val, widget)
    else:
        return var_or_val