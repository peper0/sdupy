import logging
import weakref
from _weakrefset import WeakSet

from sdupy.pyreactive.common import NotifyFunc
from sdupy.pyreactive.refresher import get_default_refresher

logger = logging.getLogger('notify')

def is_hashable(v):
    """Determine whether `v` can be hashed."""
    try:
        hash(v)
    except TypeError:
        return False
    return True


def is_notify_func(notify_func):
    return is_hashable(notify_func) and hasattr(notify_func, '__call__')


class DummyNotifier:
    def __init__(self, priority):
        self.priority = priority

    def add_observer(self, notifier: 'Notifier'):
        pass

    def remove_observer(self, notifier: 'Notifier'):
        pass

    def notify_observers(self):
        pass


def max_not_none(a, b):
    if a is None:
        return b
    elif b is None:
        return a
    else:
        return max(a, b)


def min_not_none(a, b):
    if a is None:
        return b
    elif b is None:
        return a
    else:
        return min(a, b)


all_notifiers = WeakSet()

_got_finals = 0

class ScopedName:
    names = []

    def __init__(self, name, final=False):
        self.name = name
        self.final = final

    def __enter__(self):
        global _got_finals
        if self.name is not None and _got_finals == 0:
            self.names.append(self.name)
        if self.final:
            _got_finals += 1

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _got_finals
        if self.final:
            _got_finals -= 1
        if self.name is not None and _got_finals == 0:
            res = self.names.pop()
            assert res == self.name


class Notifier:
    def __init__(self, notify_func: NotifyFunc = lambda: True):
        self._observers = weakref.WeakSet()  # type: Set[Notifier]
        self._priority = 0
        self.name = '/'.join(ScopedName.names)
        assert is_notify_func(notify_func)
        self.notify_func = notify_func
        self.calls = 0
        self.stats = dict()
        all_notifiers.add(self)
        #  lowest called first; should be greater than all observed

    def notify(self):
        return self.notify_func()  # may return awaitable

    def notify_observers(self):
        self.calls += 1
        for observer in self._observers:
            get_default_refresher().schedule_call(observer)

    def add_observer(self, observer: 'Notifier'):
        """
        :param observer: A notifier that will be notified (WARNING! it must be owned somewhere else; it's especially
                       important for bound methods or partially bound functions). It must be hashable and equality
                       comparable. If there are more than one calls to the same notifier pending, they are reduced to
                       one only. It will take part in the topological sort when obtaining an order of
                       notifications. It's priority will be enforced to be greater than the priority of this object.
        """
        self._update_observer_priority(observer)
        self._observers.add(observer)

    def _update_observer_priority(self, observer: 'Notifier'):
        observer.priority = max(observer.priority, self.priority + 1)

    def remove_observer(self, observer: 'Notifier'):
        self._observers.remove(observer)

    @property
    def priority(self):
        return self._priority

    @priority.setter
    def priority(self, value):
        assert self._priority is None or self._priority <= value
        self._priority = value
        for observer in self._observers:
            self._update_observer_priority(observer)


2
