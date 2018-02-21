import asyncio
import logging
import os
import weakref
from abc import abstractmethod
from contextlib import suppress
from typing import Any, Awaitable, Callable, Coroutine, NamedTuple, Union

CoroutineFunction = Callable[[], Coroutine]
Observer = Union[Callable[[], None], CoroutineFunction]

logger = logging.getLogger('reactive')


class QueueItem(NamedTuple):
    priority: int
    id: Any
    awaitable: Awaitable

    def __lt__(self, other):
        return self.priority < other.priority


class Refresher:
    def __init__(self):
        self.queue = asyncio.PriorityQueue()
        self.task = None  # type: asyncio.Task

    def maybe_start_task(self):
        if not self.task or self.task.done():
            self.task = asyncio.ensure_future(self.run())  # type: asyncio.Task
            self.task.add_done_callback(self._handle_done)

    @staticmethod
    def _handle_done(f):
        if f.cancelled():
            logger.warning('refresh task was cancelled')
            return
        e = f.exception()
        if e:
            logger.exception('refresh task finished with exception, rethrowing')
            raise e

    def add_coroutine(self, hash, coro):
        t = QueueItem(1, hash, coro)
        self.queue.put_nowait(t)
        self.maybe_start_task()

    async def run(self):
        update_next = None

        with suppress(asyncio.QueueEmpty):  # it's ok - if the queue is empty we just exit
            while True:
                update = update_next if update_next else self.queue.get_nowait()
                try:
                    update_next = self.queue.get_nowait()
                    if update_next.id == update.id:  # skip update if is same as next
                        continue
                except asyncio.QueueEmpty:
                    update_next = None

                try:
                    await update.awaitable
                except Exception as e:
                    logger.exception('exception when notifying observer (ignoring)')


refresher = None


async def wait_for_var(var):
    # fixme: waiting only for certain level
    await refresher.task


def get_default_refresher():
    global refresher
    if not refresher:
        refresher = Refresher()

    return refresher


# rename to "Observable"?
class VarBase:
    def __init__(self):
        self._observers = weakref.WeakSet()  # Iterable[Observer]
        self.on_dispose = None
        self.disposed = False
        self._kept_references = []

    def __del__(self):
        if not self.disposed and self.on_dispose:
            os.write(1, b"will dispose\n")
            get_default_refresher().add_coroutine(self.on_dispose, self.on_dispose())
            # assert self.disposed, "Var.dispose was not called before destroying"

    def notify_observers(self):
        for corof in self._observers:  # type: Observer
            get_default_refresher().add_coroutine(corof, ensure_coro_func(corof)())

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


def ensure_coro_func(f):
    if asyncio.iscoroutinefunction(f):
        return f
    elif hasattr(f, '__call__'):
        async def async_f(*args, **kwargs):
            return f(*args, **kwargs)

        return async_f
