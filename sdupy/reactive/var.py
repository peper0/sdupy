import logging
import os
import weakref
from abc import abstractmethod
from typing import Any, Union

from . import decorators
from .async_refresher import AsyncRefresher
from .common import Observer, VarInterface

logger = logging.getLogger('reactive')

refresher = None


async def wait_for_var(var=None):
    # fixme: waiting only for certain level (if var is not None)
    await refresher.task


def get_default_refresher():
    global refresher
    if not refresher:
        refresher = AsyncRefresher()

    return refresher


def make_rval(*args, **kwargs):
    return RVal(*args, **kwargs)


# rename to "Observable"?
class VarBase(VarInterface):
    def __init__(self):
        self._observers = weakref.WeakSet()  # Iterable[Observer]
        self.on_dispose = None
        self.disposed = False
        self._kept_references = []

    def __del__(self):
        if not self.disposed and self.on_dispose:
            get_default_refresher().schedule_call(self.on_dispose, self.on_dispose)
            # assert self.disposed, "Var.dispose was not called before destroying"

    def notify_observers(self):
        for corof in self._observers:  # type: Observer
            get_default_refresher().schedule_call(corof, corof)

    async def dispose(self):
        if not self.disposed:
            if self.on_dispose:
                await self.on_dispose()
            self.disposed = True

    def add_observer(self, observer: Observer):
        self._observers.add(observer)

    def keep_reference(self, o):
        """
        Keeps a reference to `o` for own Var instance lifetime.
        """
        self._kept_references.append(o)

    @property
    def data(self):
        return self.get()

    @data.setter
    def data(self, value):
        self.set(value)

    @abstractmethod
    def set(self, value):
        raise NotImplementedError()

    @abstractmethod
    def get(self):
        raise NotImplementedError()

    def __repr__(self):
        # print()
        return 'Var({})'.format(repr(self.data))
        # return "Var"

    def __str__(self):
        return str(self.data)
        # return "Var"

    def __bytes__(self):
        return bytes(self.data)

    def __format__(self, format_spec):
        return format(self.data)
        # return "Var"

    @decorators.reactive(args_fwd_none=[0, 1])
    def __getattr__(self_data, item):
        return getattr(self_data, item)

    # @decorators.reactive(args_fwd_none=[0, 1])
    # def __setattr__(self_data, key, value):
    #    return setattr(self_data, key, value)

    def __delattr__(self, key):
        return setattr(self.data, key)

    @decorators.reactive(args_fwd_none=[0])
    def __call__(self_data, *args, **kwargs):
        return self_data(*args, **kwargs)

    @decorators.reactive(args_fwd_none=[0])
    def __len__(self_data):
        return len(self_data)

    @decorators.reactive(args_fwd_none=[0])
    def __contains__(self_data, item):
        return item in self_data

    @decorators.reactive(args_fwd_none=[0])
    def __getitem__(self_data, item):
        return self_data[item]

    @decorators.reactive(args_fwd_none=[0])
    def __setitem__(self_data, key, value):
        self_data[key] = value

    def __delitem__(self, key, value):
        del self.data[key]

    @decorators.reactive(args_fwd_none=[0])
    def __missing__(self_data, key):
        return self_data.__missing__(key)

    @decorators.reactive(args_fwd_none=[0, 1])
    def __add__(self_data, other):
        return self_data + other

    @decorators.reactive(args_fwd_none=[0, 1])
    def __radd__(self_data, other):
        return other + self_data

    def __iadd__(self_data, other):
        self_data += other

    @decorators.reactive(args_fwd_none=[0, 1])
    def __eq__(self_data, other):
        return self_data == other

    @decorators.reactive(args_fwd_none=[0])
    def __bool__(self_data):
        return self_data.__bool__

        # TODO: rest of arithmetic and logic functions (http://www.diveintopython3.net/special-method-names.html)


class Var(VarBase):
    def __init__(self, data=None):
        super().__init__()
        self._data = data

    def set(self, value):
        self._data = value
        self.notify_observers()

    def get(self):
        return self._data


class RVal(VarBase):
    def __init__(self):
        super().__init__()
        self._data = None  # type: Union[VarBase, Any]
        self._target_var = None
        self._updater = None

    def provide(self, data_or_target):
        if isinstance(data_or_target, VarBase):
            self._target_var = data_or_target
            self._data = None
            self._updater = self.notify_observers
            self._target_var.add_observer(self._updater)
        else:
            self._target_var = None
            self._data = data_or_target
            self._updater = None
        self.notify_observers()

    def get(self):
        if self._target_var:
            return self._target_var.get()
        else:
            return self._data

    def set(self, value):
        if self._target_var:
            return self._target_var.set(value)
        else:
            raise Exception("read-only variable")


decorators.var_factory = RVal
