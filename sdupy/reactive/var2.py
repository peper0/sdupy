import asyncio
import inspect
import logging
import weakref
from abc import abstractmethod
from contextlib import contextmanager
from itertools import chain
from typing import Any, Callable, Dict, Iterable, NamedTuple, Optional, Union, overload

import asyncio_extras

from sdupy.reactive.common import CoroutineFunction, Observer
from sdupy.reactive.refresher import get_default_refresher


def is_hashable(v):
    """Determine whether `v` can be hashed."""
    try:
        hash(v)
    except TypeError:
        return False
    return True


def is_observer(observer):
    return hasattr(observer, '__call__')


class FakeObservable:
    def __init__(self, priority, id):
        self.priority = priority
        self.id = id


class Observable:
    class Item(NamedTuple):
        observer: Observer
        observable: Any  # A notifier connected with the `observer` (optional)
        # id: Any
        # priority: int

    def __init__(self):
        self._observers = weakref.WeakKeyDictionary()  # type: Dict[Observable, Observer]
        self._priority: Optional[int] = None
        #  lowest called first; should be greater than all observed

    def __del__(self):
        self.dispose()

    def dispose(self):
        pass

    def notify_observers(self):
        for observable, observer in self._observers.items():
            get_default_refresher().schedule_call(observer, observable, observable.priority)

    def add_observer(self, observer: Observer, observable):
        assert is_hashable(observable)
        assert is_observer(observer)
        # if priority is not None and priority <= self._priority:
        #    warn("priority of the observer should be greater than the priority of the observable")
        if observable:
            observable.priority = self._priority + 1
        self._observers[observable] = observer

    def remove_observer(self, observable):
        del self._observers[observable]

    @property
    def priority(self):
        return self._priority

    @priority.setter
    def priority(self, value):
        self._priority = value
        for observable, _ in self._observers.items():
            observable.priority = self._priority + 1

    @property
    def id(self):
        return id(self)


class Value(Observable):
    @abstractmethod
    def _get_raw(self):
        raise NotImplementedError

    @abstractmethod
    def _set_raw(self, value):
        raise NotImplementedError

    @abstractmethod
    def _get_exception(self):
        raise NotImplementedError

    @property
    def exception(self):
        return self._get_exception()

    @property
    def raw(self):
        if self.exception:
            raise self.exception
        return self._get_raw()

    @raw.setter
    def raw(self, value):
        self._set_raw(value)


class Constant(Value):
    def __init__(self, raw):
        super().__init__()
        self._raw = raw
        self._priority = 0  # constants are usually independent

    def _get_raw(self):
        return self._raw

    def _get_exception(self):
        return None

    def _set_raw(self, value):
        raise Exception("cannot set a constant")


def const(raw):
    return Wrapper(Constant(raw))


class SelfContainedValue(Value):
    class NotInitialized:
        pass

    NOT_INITIALIZED = NotInitialized()

    def __init__(self, raw=NOT_INITIALIZED):
        super().__init__()
        self._raw = raw
        self._exception = ValueError("not initialized") if raw is SelfContainedValue.NOT_INITIALIZED else None
        self._priority = 0  # vars are usually independent

    def _get_raw(self):
        return self._raw

    def _get_exception(self):
        return self._exception

    def _set_raw(self, value):
        self._raw = value
        self._exception = None
        self.notify_observers()

    def set_exception(self, e):
        self._exception = e
        self._raw = None
        self.notify_observers()


def var(raw=SelfContainedValue.NOT_INITIALIZED):
    return Wrapper(SelfContainedValue(raw))


def raw(wrapper):
    return wrapper.OBS.raw


def is_wrapper(v):
    return hasattr(v, 'OBS') and hasattr(v.OBS,
                                         'exception')  # checking for 'raw' member here is risky since hasattr calls it...


def is_observable(v):
    return isinstance(v, Observable)


def is_value(v):
    return is_observable(v) and hasattr(v, 'raw')


def args_need_reaction(args: tuple, kwargs: dict):
    return any((is_wrapper(arg) for arg in args + tuple(kwargs.values())))


def rewrap_args(args, kwargs, args_names, args_as_vars) -> Dict[str, Any]:
    def as_value(arg):
        if is_wrapper(arg):
            return raw(arg)
        else:
            return arg

    def as_var(arg):
        if is_wrapper(arg):
            return arg
        else:
            return const(arg)

    def rewrap(index, name, arg):
        try:
            if index in args_as_vars or name in args_as_vars:
                return as_var(arg)
            else:
                return as_value(arg)
        except Exception as exception:
            raise Exception("propagating exception from arg '{}'".format(name or index)) from exception

    def arg_name(index):
        return args_names[index] if index < len(args_names) else None

    return ([rewrap(index, arg_name(index), arg) for index, arg in enumerate(args)],
            {name: rewrap(None, name, arg) for name, arg in kwargs})


def maybe_observe(arg, observer, observable):
    if is_wrapper(arg):
        return arg.OBS.add_observer(observer, observable)


def observe_args(args, kwargs, observer, observable):
    for arg in chain(args, kwargs.values()):
        maybe_observe(arg, observer, observable)


class Reactive:
    def __init__(self, args_as_vars, other_deps, dep_only_args):
        self.dep_only_args = dep_only_args
        self.other_deps = other_deps
        self.args_as_vars = args_as_vars

    def __call__(self, func):
        """
        Decorate the function.
        """
        if asyncio.iscoroutinefunction(func):
            value_provider_factory = AsyncValueProvider
        elif hasattr(func, '__call__'):
            value_provider_factory = SyncValueProvider
        else:
            raise Exception("{} is neither a function nor a coroutine function (async def...)".format(repr(func)))
        return DecoratedFunction(self, value_provider_factory, func)


class ReactiveCm(Reactive):
    def __call__(self, func):
        """
        Decorate the function.
        """
        if hasattr(func, '_isasync') and func._isasync:
            value_provider_factory = AsyncCmValueProvider
        elif hasattr(func, '__call__'):
            value_provider_factory = CmValueProvider
        else:
            raise Exception("{} is neither a function nor a coroutine function (async def...)".format(repr(func)))
        return DecoratedFunction(self, value_provider_factory, func)


class DecoratedFunction:
    def __init__(self, decorator: Reactive, factory, func: Union[CoroutineFunction, Callable]):
        self.decorator = decorator
        self.factory = factory
        self.callable = func
        self.signature = inspect.signature(func)
        self.args_names = list(self.signature.parameters)

    def __call__(self, *args, **kwargs):
        """
        Bind arguments, call function once and schedule it to be called on any arguments change.
        """
        res = Wrapper(self.factory(self, args, kwargs))
        return res.OBS.update(res)


class ValueProvider(Value):
    def __init__(self, decorated: DecoratedFunction, args, kwargs):
        super().__init__()
        self._result = None
        self._exception = None
        self.decorated = decorated
        self._get_value = None  # type: Callable[[], Value]

        # use dep_only_args
        for name in decorated.decorator.dep_only_args:
            if name in kwargs:
                maybe_observe(kwargs[name], self.update, self)
                del kwargs[name]

        # use other_deps
        for dep in decorated.decorator.other_deps:
            maybe_observe(dep, self.update, self)

        if decorated.signature:
            # support default parameters
            bound_args = decorated.signature.bind(*args, **kwargs)  # type: inspect.BoundArguments
            bound_args.apply_defaults()
            self.args = bound_args.args
            self.kwargs = bound_args.kwargs
        else:
            self.args = args
            self.kwargs = kwargs

        observe_args(self.args, self.kwargs, self.update, self)

    @contextmanager
    def _handle_exception(self):
        try:
            yield
            self._exception = None
        except Exception as e:
            self._exception = e

    def _call(self):
        # returns one of:
        # - the result,
        # - a coroutine (to be awaited),
        # - a generator to be run once and finalized before the next call
        # - an async generator
        args, kwargs = rewrap_args(self.args, self.kwargs, self.decorated.args_names,
                                   self.decorated.decorator.args_as_vars)
        return self.decorated.callable(*args, **kwargs)

    def _provide(self, result):
        self._unobserve_value()
        if is_wrapper(result):
            self._get_value = self._get_value_basic
        elif is_value(result):
            self._get_value = self._get_value_from_wrapper
        else:
            self._get_value = None
        self._result = result
        self._exception = None
        self._observe_value()
        self.notify_observers()

    def _get_value_basic(self):
        return self._result

    def _get_value_from_wrapper(self):
        return self._result.OBS

    def _set_raw(self, value):
        if self._get_value:
            self._get_value().raw = value
        else:
            raise ValueError('read-only variable')

    def _get_raw(self):
        return self._get_value().raw if self._get_value else self._result

    def _get_exception(self):
        return self._get_value().exception if self._get_value else self._exception

    def _unobserve_value(self):
        if self._get_value:
            return self._get_value().remove_observer(self)

    def _observe_value(self):
        if self._get_value:
            return self._get_value().add_observer(self, self.notify_observers())

    @abstractmethod
    def update(self, retval=None):
        pass


class SyncValueProvider(ValueProvider):
    def update(self, retval=None):
        with self._handle_exception():
            res = self._call()
            self._provide(res)
        return retval


class AsyncValueProvider(ValueProvider):
    async def update(self, retval=None):
        with self._handle_exception():
            res = await self._call()
            self._provide(res)
        return retval


class CmValueProvider(ValueProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cm = None

    def update(self, retval=None):
        self._cleanup()

        with self._handle_exception():
            self.cm = self._call()
            res = self.cm.__enter__()
            self._provide(res)
        return retval

    def dispose(self):
        self._cleanup()
        super().dispose()

    def _cleanup(self):
        try:
            if self.cm:
                self.cm.__exit__(None, None, None)
                self.cm = None
        except Exception:
            logging.exception("ignoring exception in cleanup")


class AsyncCmValueProvider(ValueProvider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cm = None

    async def update(self, retval=None):
        await self._cleanup()

        with self._handle_exception():
            self.cm = self._call()
            res = await self.cm.__aenter__()
            self._provide(res)
        return retval

    def dispose(self):
        asyncio.ensure_future(self._cleanup())
        super().dispose()

    async def _cleanup(self):
        try:
            if self.cm:
                cm = self.cm
                self.cm = None
                await cm.__aexit__(None, None, None)
        except Exception:
            logging.exception("ignoring exception in cleanup")


@overload
def reactive(f: Callable) -> Callable:
    pass


@overload
def reactive(args_as_vars: Iterable[str] = None,
             other_deps: Iterable[str] = None,
             dep_only_args: Iterable[str] = None) -> Callable:
    pass


def reactive(args_as_vars: Iterable[str] = None,
             other_deps: Iterable[str] = None,
             dep_only_args: Iterable[str] = None):
    if callable(args_as_vars):
        # a shortcut that allows simple @reactive instead of @reactive()
        return reactive()(args_as_vars)

    args_as_vars = set(args_as_vars or [])
    dep_only_args = set(dep_only_args or [])
    other_deps = other_deps or []

    return Reactive(args_as_vars=args_as_vars, other_deps=other_deps, dep_only_args=dep_only_args)


@overload
def reactive_finalizable(f: Callable) -> Callable:
    pass


@overload
def reactive_finalizable(args_as_vars: Iterable[str] = None,
                         other_deps: Iterable[str] = None,
                         dep_only_args: Iterable[str] = None) -> Callable:
    pass


def reactive_finalizable(args_as_vars: Iterable[str] = None,
                         other_deps: Iterable[str] = None,
                         dep_only_args: Iterable[str] = None):
    if callable(args_as_vars):
        # a shortcut that allows simple @reactive instead of @reactive()
        return reactive_finalizable()(args_as_vars)

    args_as_vars = set(args_as_vars or [])
    dep_only_args = set(dep_only_args or [])
    other_deps = other_deps or []

    deco = ReactiveCm(args_as_vars, dep_only_args, other_deps)

    def wrap(f):
        if inspect.isasyncgenfunction(f):
            ff = asyncio_extras.async_contextmanager(f)
            ff._isasync = True

            return deco(ff)
        else:
            return deco(contextmanager(f))

    return wrap


class Wrapper:
    def __init__(self, observable):
        self._observable = observable

    @property
    def OBS(self):
        return self._observable

    def __repr__(self):
        # print()
        if self.exception():
            return '{}(exception={})'.format(self.__class__.__name__, repr(self.exception()))
        else:
            return '{}({})'.format(self.__class__.__name__, repr(self.raw))
        # return "Var"

    def __str__(self):
        return str(self.raw)
        # return "Var"

    def __bytes__(self):
        return bytes(self.raw)

    def __format__(self, format_spec):
        return format(self.raw)
        # return "Var"

    @reactive
    def __getattr__(self_raw, item):
        return getattr(self_raw, item)

    # @reactive
    # def __setattr__(self_raw, key, value):
    #    return setattr(self_raw, key, value)

    def __delattr__(self, key):
        return setattr(self.raw, key)

    @reactive
    def __call__(self_raw, *args, **kwargs):
        return self_raw(*args, **kwargs)

    @reactive
    def __len__(self_raw):
        return len(self_raw)

    @reactive
    def __contains__(self_raw, item):
        return item in self_raw

    @reactive
    def __getitem__(self_raw, item):
        return self_raw[item]

    @reactive
    def __setitem__(self_raw, key, value):
        self_raw[key] = value

    def __delitem__(self, key, value):
        del self.raw[key]

    @reactive
    def __missing__(self_raw, key):
        return self_raw.__missing__(key)

    @reactive
    def __add__(self_raw, other):
        return self_raw + other

    @reactive
    def __sub__(self_raw, other):
        return self_raw - other

    @reactive
    def __mul__(self_raw, other):
        return self_raw * other

    @reactive
    def __truediv__(self_raw, other):
        return self_raw / other

    @reactive
    def __floordiv__(self_raw, other):
        return self_raw // other

    @reactive
    def __radd__(self_raw, other):
        return other + self_raw

    def __iadd__(self_raw, other):
        self_raw += other

    @reactive
    def __eq__(self_raw, other):
        return self_raw == other

    def __bool__(self):
        return self.raw.__bool__()

        # TODO: rest of arithmetic and logic functions (http://www.diveintopython3.net/special-method-names.html)
