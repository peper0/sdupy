from contextlib import suppress

from PyQt5.QtWidgets import QWidget

from sdupy.pyreactive import Wrapped, is_wrapper
from sdupy.pyreactive.notifier import ScopedName
from sdupy.pyreactive.refresher import logger as notify_logger
from sdupy.pyreactive.var import Proxy
from sdupy.utils import trace


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