import weakref
from _weakrefset import WeakSet
from typing import Dict, Iterable, Union
from weakref import WeakKeyDictionary

from sdupy.reactive.common import NotifyFunc
from sdupy.reactive.refresher import get_default_refresher


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

    def add_observer(self, notify_func: NotifyFunc, notifiers: Union['Notifier', Iterable['Notifier'], None]):
        pass

    def remove_observer(self, notify_func: NotifyFunc):
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
stats_for_notify_func = WeakKeyDictionary()  # type: Dict[NotifyFunc, Dict]


class Notifier:
    class Observer:
        def __init__(self, notifiers, notify_func: NotifyFunc, name):
            self.priority = None  # we start from 0, then it can be increased but never decreased
            self.notifiers = WeakSet(notifiers)
            self.stats = stats_for_notify_func.setdefault(notify_func, dict(name=name))

    def __init__(self, name):
        self._observers = weakref.WeakKeyDictionary()  # type: Dict[NotifyFunc, self.Observer]
        self._priority = 0
        self.name = name
        self.calls = 0
        all_notifiers.add(self)
        #  lowest called first; should be greater than all observed

    def notify_observers(self):
        self.calls += 1
        for notify_func, observer in self._observers.items():
            get_default_refresher().schedule_call(notify_func, notify_func, observer.priority, observer.stats)

    def add_observer(self, notify_func: NotifyFunc, notifiers: Union['Notifier', Iterable['Notifier'], None],
                     name=None):
        """

        :param notify_func: A callback that will be called (WARNING! it must be owned somewhere else; it's especially
                       important for bound methods or partially bound functions). It must be hashable and equality
                       comparable. If there are more than one calls to `notify` pending, they are reduced to one only.
        :param notifiers: A notifiers that will take part in the topological sort when obtaining an order of
                         notifications. Their priority will be enforced to be greater than the priority of this object.
        :return:
        """
        assert is_notify_func(notify_func)
        # if priority is not None and priority <= self._priority:
        #    warn("priority of the observer should be greater than the priority of the observable")
        if notifiers is None:
            notifiers = []
        if not hasattr(notifiers, '__iter__'):
            notifiers = [notifiers]
        observer = self.Observer(notifiers, notify_func, name or notify_func.__name__)
        self._update_observer_priority(observer)
        self._observers[notify_func] = observer

    def _update_observer_priority(self, observer: 'Notifier.Observer'):
        """
        Set priorities of all notifers depending on given observer to be greater than ours and save min of them in the
        observer
        """
        priority = None
        for notifier in observer.notifiers:
            notifier.priority = max_not_none(notifier.priority, self.priority + 1)
            priority = min_not_none(priority, notifier.priority)
        observer.priority = priority if priority is not Notifier else self.priority + 1

    def remove_observer(self, notify_func: NotifyFunc):
        del self._observers[notify_func]

    @property
    def priority(self):
        return self._priority

    @priority.setter
    def priority(self, value):
        assert self._priority is None or self._priority <= value
        self._priority = value
        for observer in self._observers.values():
            self._update_observer_priority(observer)


2
