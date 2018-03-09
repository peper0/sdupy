import asyncio
from abc import abstractmethod
from typing import Callable, Coroutine, Union


def ensure_coro_func(f):
    if asyncio.iscoroutinefunction(f):
        return f
    elif hasattr(f, '__call__'):
        async def async_f(*args, **kwargs):
            return f(*args, **kwargs)

        return async_f


CoroutineFunction = Callable[[], Coroutine]
Observer = Union[Callable[[], None], CoroutineFunction]


class VarInterface:
    @abstractmethod
    def notify_observers(self):
        raise NotImplementedError()

    @abstractmethod
    def add_observer(self, observer: Observer):
        raise NotImplementedError()

    @abstractmethod
    def keep_reference(self, o):
        """
        Keeps a reference to `o` for own Var instance lifetime.
        """
        raise NotImplementedError()

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

    @abstractmethod
    def exception(self):
        raise NotImplementedError()
