import asyncio
import inspect
import logging
from abc import abstractmethod
from contextlib import contextmanager
from itertools import chain
from typing import Any, Dict, List, Set, Tuple

from .common import WrapperInterface, is_wrapper, unwrapped
from .decorators import DecoratedFunction
from .forwarder import ConstForwarders, MutatingForwarders
from .notifier import DummyNotifier, Notifier


class Wrapper(WrapperInterface):
    def __init__(self, raw=None, name=None):
        self._notifier = Notifier(name)
        self._exception = None  # type: Exception
        self._raw = raw

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


class Constant(WrapperInterface, ConstForwarders):
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


class Var(Wrapper, ConstForwarders, MutatingForwarders):
    NOT_INITIALIZED = NotInitializedError()

    def __init__(self, raw=NOT_INITIALIZED, name=None):
        super().__init__(name=name)
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
    return hasattr(v, '__notifier__') or hasattr(v, '__observable__')


def wrap(v):
    # TODO: do magic with selecting proper wrapper or reusing one if was done already for this object
    return const(v)


def as_observable(v):
    if is_observable(v):
        return v
    else:
        return wrap(v)


class ArgsHelper:
    def __init__(self, args, kwargs, signature, callable):
        if signature:
            # support default parameters
            try:
                bound_args = signature.bind(*args, **kwargs)  # type: inspect.BoundArguments
                bound_args.apply_defaults()
            except Exception as e:
                raise Exception('during binding {}{}'.format(callable.__name__, signature)) from e
            args_names = list(signature.parameters)

            self.args = bound_args.args
            self.kwargs = bound_args.kwargs
            self.args_names = args_names[0:len(self.args)]
            self.args_names += [None] * (len(self.args) - len(self.args_names))
            self.kwargs_indices = [(args_names.index(name) if name in args_names else None)
                                   for name in self.kwargs.keys()]
        else:
            self.args = args
            self.kwargs = kwargs
            self.args_names = [None] * len(self.args)
            self.kwargs_indices = [None] * len(self.kwargs)

    def iterate_args(self):
        return ((index, name, arg) for name, (index, arg) in zip(self.args_names, enumerate(self.args)))

    def iterate_kwargs(self):
        return ((index, name, arg) for index, (name, arg) in zip(self.kwargs_indices, self.kwargs.items()))


def rewrap_args(args_helper: ArgsHelper, pass_args) -> Tuple[List[Any], Dict[str, Any]]:
    def rewrap(index, name, arg):
        try:
            if index in pass_args or name in pass_args:
                return arg
            else:
                return unwrapped(arg)
        except Exception as exception:
            raise ArgumentError(name or str(index)) from exception

    return ([rewrap(index, name, arg) for index, name, arg in args_helper.iterate_args()],
            {name: rewrap(index, name, arg) for index, name, arg in args_helper.iterate_kwargs()})


def observe(arg, notify_callback, notifiers):
    if isinstance(arg, Notifier):
        return arg.add_observer(notify_callback, notifiers)
    else:
        return arg.__notifier__.add_observer(notify_callback, notifiers)


def maybe_observe(arg, notify_callback, notifiers):
    if is_wrapper(arg):
        observe(arg, notify_callback, notifiers)


def observe_args(args_helper: ArgsHelper, pass_args: Set[str], notify_callback, notifiers):
    for index, name, arg in chain(args_helper.iterate_args(), args_helper.iterate_kwargs()):
        if index not in pass_args and name not in pass_args:
            maybe_observe(arg, notify_callback, notifiers)


class Proxy(WrapperInterface, ConstForwarders):
    """
    A proxy to any observable object (possibly another proxy or some Wrapper like Var or Const). It tries to behave
    exactly like the object itself.

    It must implement WrapperInterface since it's possible that the object inside implements it. If the
    Proxy was given as a parameter to the @reactive function, it should be observed and unwrapped.
    """

    def __init__(self, name):
        super().__init__()
        self._ref = Var()
        self._notifier = Notifier(name=name)
        self._notify_observers = self._notifier.notify_observers  # hold ref for notifier
        self._ref.__notifier__.add_observer(self._notify_observers, self._notifier)

    @property
    def __notifier__(self):
        return self._notifier

    @property
    def __inner__(self):
        ref = self._ref.__inner__
        if ref is not None and hasattr(ref, '__inner__'):
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
        if ref is not None and hasattr(ref, '__notifier__'):
            return ref.__notifier__.remove_observer(self._notify_observers)

    def _observe_value(self):
        ref = self._get_ref()
        if ref is not None and hasattr(ref, '__notifier__'):
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
        super().__init__(name=decorated.callable.__name__)
        self.decorated = decorated
        self._update_ref_holder = HashableCallable(self._update, (id(self), ReactiveProxy._update))

        # use dep_only_args
        for name in decorated.decorator.dep_only_args:
            if name in kwargs:
                arg = kwargs[name]  # fixme use "pop"
                if hasattr(arg, '__iter__'):
                    for a in arg:
                        observe(a, self._update_ref_holder, self.__notifier__)
                else:
                    observe(arg, self._update_ref_holder, self.__notifier__)

                del kwargs[name]

        # use other_deps
        for dep in decorated.decorator.other_deps:
            maybe_observe(dep, self._update_ref_holder, self.__notifier__)

        self.args_helper = ArgsHelper(args, kwargs, decorated.signature, decorated.callable)
        self.args = self.args_helper.args
        self.kwargs = self.args_helper.kwargs

        observe_args(self.args_helper, self.decorated.decorator.pass_args, self._update_ref_holder, self.__notifier__)

    @contextmanager
    def _handle_exception(self, reraise):
        try:
            yield
        except Exception as e:
            self._ref.set_exception(e)
            if reraise:
                if not isinstance(e, ArgumentError):
                    # ArgumentError is not re-raised since it was
                    raise e

    def _call(self):
        # returns one of:
        # - the result,
        # - a coroutine (to be awaited),
        # - a generator to be run once and finalized before the next call
        # - an async generator
        args, kwargs = rewrap_args(self.args_helper, self.decorated.decorator.pass_args)
        return self.decorated.callable(*args, **kwargs)

    @abstractmethod
    def _update(self, retval=None, reraise=False):
        pass


class SyncReactiveProxy(ReactiveProxy):
    def _update(self, retval=None, reraise=False):
        with self._handle_exception(reraise):
            res = self._call()
            self._set_ref(res)
        return retval


class AsyncReactiveProxy(ReactiveProxy):
    async def _update(self, retval=None, reraise=False):
        with self._handle_exception(reraise):
            res = await self._call()
            self._set_ref(res)
        return retval


class CmReactiveProxy(ReactiveProxy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cm = None

    def _update(self, retval=None, reraise=False):
        self._cleanup()

        with self._handle_exception(reraise):
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

    async def _update(self, retval=None, reraise=False):
        await self._cleanup()

        with self._handle_exception(reraise):
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
