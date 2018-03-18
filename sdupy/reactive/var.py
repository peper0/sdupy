import asyncio
import inspect
import logging
from abc import abstractmethod
from contextlib import contextmanager
from itertools import chain
from typing import Any, Dict, List, Tuple

from sdupy.reactive.common import WrapperInterface, is_wrapper, unwrapped
from .decorators import DecoratedFunction
from .forwarder import CommonForwarders
from .notifier import DummyNotifier, Notifier


class Wrapper(WrapperInterface):
    def __init__(self):
        self._notifier = Notifier()
        self._exception = None  # type: Exception
        self._raw = None

    @property
    def __notifier__(self):
        return self._notifier

    @property
    def __inner__(self):
        if self._exception:
            raise self._exception
        return self._raw

    def _target(self):
        return self

    def __repr__(self):
        # print()
        try:
            return '{}({})'.format(self.__class__.__name__, repr(self.__inner__))
        except Exception as e:
            return '{}(exception={})'.format(self.__class__.__name__, repr(e))


class Constant(WrapperInterface, CommonForwarders):
    dummy_notifier = DummyNotifier(priority=0)

    def __init__(self, raw):
        super().__init__()
        self._raw = raw

    @property
    def __notifier__(self):
        return self.dummy_notifier

    @property
    def __inner__(self):
        return self._raw

    def _target(self):
        return self


def const(raw):
    return Constant(raw)


class NotInitializedError(Exception):
    def __init__(self):
        super().__init__('not initialized')


class ArgumentError(Exception):
    def __init__(self, arg_name):
        super().__init__("propagating exception from arg '{}'".format(arg_name))
        self.arg_name = arg_name


class Var(Wrapper, CommonForwarders):
    NOT_INITIALIZED = NotInitializedError()

    def __init__(self, raw=NOT_INITIALIZED):
        super().__init__()
        if raw is self.NOT_INITIALIZED:
            self.set_exception(NotInitializedError())
        else:
            self.set(raw)

    def set(self, value):
        self._raw = value
        self._exception = None
        self._notifier.notify_observers()

    def set_exception(self, e):
        self._exception = e
        self._raw = None
        self._notifier.notify_observers()

    # noinspection PyMethodOverriding
    @Wrapper.__inner__.setter
    def __inner__(self, value):
        return self.set(value)

    def __imatmul__(self, other):
        """
        A syntax sugar (at the expense of some inconsistency and inconvenience when we want to make @= on the inner)
        """
        self.set(other)
        return self


def var(raw=Var.NOT_INITIALIZED):
    return Var(raw)


def is_observable(v):
    """
    Check whether given object should be considered as "observable" i.e. the object that manages notifiers internally
    and returns observable objects from it's methods.
    """
    return hasattr(v, '__observable__')


def wrap(v):
    # TODO: do magic with selecting proper wrapper or reusing one if was done already for this object
    return const(v)


def as_observable(v):
    if is_observable(v):
        return v
    else:
        return wrap(v)


def rewrap_args(args, kwargs, args_names, args_as_vars) -> Tuple[List[Any], Dict[str, Any]]:
    def rewrap(index, name, arg):
        try:
            if index in args_as_vars or name in args_as_vars:
                return as_observable(arg)
            else:
                return unwrapped(arg)
        except Exception as exception:
            raise ArgumentError(name or str(index)) from exception

    def arg_name(index):
        return args_names[index] if index < len(args_names) else None

    return ([rewrap(index, arg_name(index), arg) for index, arg in enumerate(args)],
            {name: rewrap(None, name, arg) for name, arg in kwargs})


def maybe_observe(arg, notify_callback, notifiers):
    if is_wrapper(arg):
        return arg.__notifier__.add_observer(notify_callback, notifiers)


def observe_args(args, kwargs, notify_callback, notifiers):
    for arg in chain(args, kwargs.values()):
        maybe_observe(arg, notify_callback, notifiers)


class Proxy(WrapperInterface, CommonForwarders):
    """
    A proxy to any observable object (possibly another proxy or some Wrapper like Var or Const). It tries to behave
    exactly like the object itself.

    It must implement WrapperInterface since it's possible that the object inside implements it. If the
    Proxy was given as a parameter to the @reactive function, it should be observed and unwrapped.
    """

    def __init__(self):
        super().__init__()
        self._ref = Var()
        self._notifier = Notifier()
        self._notify_observers = self._notifier.notify_observers  # hold ref for notifier
        self._ref.__notifier__.add_observer(self._notify_observers, self._notifier)

    @property
    def __notifier__(self):
        return self._notifier

    @property
    def __inner__(self):
        ref = self._ref.__inner__
        if ref and hasattr(ref, '__inner__'):
            return ref.__inner__

    def _target(self):
        return self._ref

    def _get_ref(self):
        try:
            return self._ref.__inner__
        except Exception:
            return None

    def _set_ref(self, ref):
        self._unobserve_value()
        self._ref @= as_observable(ref)
        self._observe_value()

    def _unobserve_value(self):
        ref = self._get_ref()
        if ref and hasattr(ref, '__notifier__'):
            return ref.__notifier__.remove_observer(self)

    def _observe_value(self):
        ref = self._get_ref()
        if ref and hasattr(ref, '__notifier__'):
            return ref.__notifier__.add_observer(self._notify_observers, self._notifier)

    def __getattr__(self, item):
        # FIXME: optional proxying result (if returned value is proxy)
        return getattr(self._target().__inner__, item)

    # TODO: other forwarders


class HashableCallable:
    def __init__(self, callable, uid):
        self.callable = callable
        self.uid = uid

    def __call__(self, *args, **kwargs):
        return self.callable(*args, **kwargs)

    def __hash__(self):
        return hash(self.uid)

    def __getattr__(self, item):
        return getattr(self.callable, item)

    def __eq__(self, other):
        return isinstance(other, HashableCallable) and self.uid == other.uid


class ReactiveProxy(Proxy):
    def __init__(self, decorated: DecoratedFunction, args, kwargs):
        super().__init__()
        self.decorated = decorated
        self._update_ref_holder = HashableCallable(self._update, (id(self), ReactiveProxy._update))

        # use dep_only_args
        for name in decorated.decorator.dep_only_args:
            if name in kwargs:
                maybe_observe(kwargs[name], self._update_ref_holder, self.__notifier__)
                del kwargs[name]

        # use other_deps
        for dep in decorated.decorator.other_deps:
            maybe_observe(dep, self._update_ref_holder, self.__notifier__)

        if decorated.signature:
            # support default parameters
            bound_args = decorated.signature.bind(*args, **kwargs)  # type: inspect.BoundArguments
            bound_args.apply_defaults()
            self.args = bound_args.args
            self.kwargs = bound_args.kwargs
        else:
            self.args = args
            self.kwargs = kwargs

        observe_args(self.args, self.kwargs, self._update_ref_holder, self.__notifier__)

    @contextmanager
    def _handle_exception(self):
        try:
            yield
        except Exception as e:
            self._ref.set_exception(e)

    def _call(self):
        # returns one of:
        # - the result,
        # - a coroutine (to be awaited),
        # - a generator to be run once and finalized before the next call
        # - an async generator
        args, kwargs = rewrap_args(self.args, self.kwargs, self.decorated.args_names,
                                   self.decorated.decorator.args_as_vars)
        return self.decorated.callable(*args, **kwargs)

    @abstractmethod
    def _update(self, retval=None):
        pass


class SyncReactiveProxy(ReactiveProxy):
    def _update(self, retval=None):
        with self._handle_exception():
            res = self._call()
            self._set_ref(res)
        return retval


class AsyncReactiveProxy(ReactiveProxy):
    async def _update(self, retval=None):
        with self._handle_exception():
            res = await self._call()
            self._set_ref(res)
        return retval


class CmReactiveProxy(ReactiveProxy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cm = None

    def _update(self, retval=None):
        self._cleanup()

        with self._handle_exception():
            self.cm = self._call()
            res = self.cm.__enter__()
            self._set_ref(res)
        return retval

    def __del__(self):
        self._cleanup()

    def _cleanup(self):
        try:
            if self.cm:
                self.cm.__exit__(None, None, None)
                self.cm = None
        except Exception:
            logging.exception("ignoring exception in cleanup")


class AsyncCmReactiveProxy(ReactiveProxy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cm = None

    async def _update(self, retval=None):
        await self._cleanup()

        with self._handle_exception():
            self.cm = self._call()
            res = await self.cm.__aenter__()
            self._set_ref(res)
        return retval

    def __del__(self):
        asyncio.ensure_future(self._cleanup())

    async def _cleanup(self):
        try:
            if self.cm:
                cm = self.cm
                self.cm = None
                await cm.__aexit__(None, None, None)
        except Exception:
            logging.exception("ignoring exception in cleanup")
