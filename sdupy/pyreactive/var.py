import asyncio
import inspect
import logging
from abc import abstractmethod
from builtins import NotImplementedError
from contextlib import contextmanager, suppress
from inspect import iscoroutinefunction
from itertools import chain
from typing import Any, Dict, List, Set, Tuple

from sdupy.pyreactive.decorators import HideStackHelper, hide_nested_calls, stop_hiding_nested_calls
from .common import Wrapped, is_wrapper, unwrapped
from .decorators import DecoratedFunction, reactive
from .forwarder import ConstForwarders, MutatingForwarders
from .notifier import DummyNotifier, Notifier, ScopedName


class Wrapper(Wrapped):
    def __init__(self, raw=None):
        self._notifier = Notifier(self._notify)
        self._exception = None  # type: Exception
        self._raw = raw

    def _notify(self):
        raise NotImplementedError()

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

    def __str__(self):
        try:
            return '{}({})'.format(self.__class__.__name__, repr(self.__inner__))
        except Exception as e:
            return '{}(exception={})'.format(self.__class__.__name__, repr(e))


class Constant(Wrapped, ConstForwarders):
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

    #Not sure whether we should simply forward it without @reactive
    #without @reactive const(v).something() is not reactive anymore, which is bad
    #so let's see what happens if we change it...
    @reactive
    def __getattr__(self, item):
        #return getattr(self._target().__inner__, item)
        return getattr(self, item)


def const(raw):
    return Constant(raw)


class NotInitializedError(Exception):
    def __init__(self):
        super().__init__('not initialized')


class SilentError(Exception):
    """
    An exception that is silently propagated and not raised unless explicit unwrapping is done on the variable.
    The error that is silenced should be the cause of this error.
    """
    pass


class ArgEvalError(Exception):
    """
    A reactive argument is in error state. The argument error should be the cause of this error.
    """
    def __init__(self, arg_name, function_name):
        super().__init__("error in argument '{}' of '{}'".format(arg_name, function_name))
        self.arg_name = arg_name
        self.function_name = function_name


class Var(Wrapper, ConstForwarders, MutatingForwarders):
    NOT_INITIALIZED = NotInitializedError()

    def __init__(self, raw=NOT_INITIALIZED, name=None):
        with ScopedName(name):
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

    def _notify(self):
        pass

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

    #Not sure whether we should simply forward it (see Const.__getattr__)
    def __getattr__(self, item):
        return getattr(self._target().__inner__, item)



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
    @stop_hiding_nested_calls
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


def rewrap_args(args_helper: ArgsHelper, pass_args, func_name) -> Tuple[List[Any], Dict[str, Any]]:
    def rewrap(index, name, arg):
        try:
            if index in pass_args or name in pass_args:
                return arg
            else:
                return unwrapped(arg)
        except Exception as exception:
            e = ArgEvalError(name or str(index), func_name)
            e.__cause__ = exception
            raise SilentError() from e

    return ([rewrap(index, name, arg) for index, name, arg in args_helper.iterate_args()],
            {name: rewrap(index, name, arg) for index, name, arg in args_helper.iterate_kwargs()})


def observe(arg, notifier):
    if isinstance(arg, Notifier):
        return arg.add_observer(notifier)
    else:
        return arg.__notifier__.add_observer(notifier)


def maybe_observe(arg, notifier):
    if is_wrapper(arg):
        observe(arg, notifier)


def observe_args(args_helper: ArgsHelper, pass_args: Set[str], notifier):
    for index, name, arg in chain(args_helper.iterate_args(), args_helper.iterate_kwargs()):
        if index not in pass_args and name not in pass_args:
            maybe_observe(arg, notifier)


class Proxy(Wrapped, ConstForwarders, MutatingForwarders):
    def __init__(self, other_var: Wrapped):
        assert other_var is not None
        super().__init__()
        self._notifier = Notifier()
        self._other_var = other_var
        self._other_var.__notifier__.add_observer(self._notifier)

    @property
    def __notifier__(self):
        return self._notifier

    def _target(self):
        return self._other_var

    @property
    def __inner__(self):
        return self._other_var.__inner__

    def __getattr__(self, item):
        return getattr(self._target().__inner__, item)


class VolatileProxy(Proxy):
    def __init__(self, other_var: Wrapped):
        with ScopedName('volatile'):
            super().__init__(other_var)
        self._notifier.notify_func = self._trigger

    def _trigger(self):
        with suppress(Exception):
            self._other_var.__inner__  # trigger run even if the result is not used
        return True


class SwitchableProxy(Wrapped, ConstForwarders):
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
            return ref.__notifier__.remove_observer(self._notifier)

    def _observe_value(self):
        ref = self._get_ref()
        if ref is not None and hasattr(ref, '__notifier__'):
            return ref.__notifier__.add_observer(self._notifier)

    @reactive
    def __getattr__(self, item):
        return getattr(self, item)


updates_stack = []


def obtain_call_line():
    return None
    #FIXME: finish this
    import traceback
    return traceback.extract_stack()


class LazySwitchableProxy(Wrapped, ConstForwarders):
    """
    A proxy to any observable object (possibly another proxy or some Wrapper like Var or Const). It tries to behave
    exactly like the object itself.

    It must implement WrapperInterface since it's possible that the object inside implements it. If the
    Proxy was given as a parameter to the @reactive function, it should be observed and unwrapped.
    """

    def __init__(self, async):
        super().__init__()
        self.async = async
        self._ref = None
        self._dirty = False
        if async:
            # I have no idea how to call do lazy updating if update is async (and getter isn't)
            self._notifier = Notifier(self._update_async)
        else:
            self._notifier = Notifier(self._args_changed)
            self._dirty = True
        self._exception = None
        self._notifier.line = obtain_call_line()

    @property
    def __notifier__(self):
        return self._notifier

    @property
    def __inner__(self):
        try:
            self._update_if_dirty()

            if self._exception is not None:
                raise self._exception
    #            if isinstance(self._exception, SilentError):
    #                raise self._exception
                #raise Exception() from self._exception
            if self._ref is not None and hasattr(self._ref, '__inner__'):
                return self._ref.__inner__
        except AttributeError as e:
            # AttributeError could be interpreted as 'no such method' on at some point of the call stack
            raise Exception("Disabling AttributeError") from e

    def _target(self):
        self._update_if_dirty()
        if self._ref is None:
            raise NotInitializedError()
        return self._ref

    def _get_ref(self):
        try:
            return self._ref
        except Exception:
            return None

    def _set_ref(self, ref):
        self._unobserve_value()
        self._ref = as_observable(ref)
        self._exception = None
        self._observe_value()

    def _unobserve_value(self):
        ref = self._get_ref()
        if ref is not None and hasattr(ref, '__notifier__'):
            return ref.__notifier__.remove_observer(self._notifier)

    def _observe_value(self):
        ref = self._get_ref()
        if ref is not None and hasattr(ref, '__notifier__'):
            return ref.__notifier__.add_observer(self._notifier)

    @reactive
    def __getattr__(self, item):
        return getattr(self, item)

    def _update_if_dirty(self):
        if self._dirty:
            # FIXME: doesn't work for async updates
            #logger.debug('updating {}'.format(self._notifier.name))
            updates_stack.append(self._notifier.line)
            try:
                hide_nested_calls(self._update)()
            except Exception as e:
                #import traceback
                #print(traceback.print_stack())
                logging.exception('error when updating {}'.format(self._notifier.name))
                #logging.exception('error when updating {}'.format(
                #    '\n======\n'.join(['\n'.join(map(str, l)) for l in updates_stack])))
            updates_stack.pop()
            self._dirty = False

    def _args_changed(self):
        assert not iscoroutinefunction(self._update)
        self._dirty = True
        return True

    @hide_nested_calls
    async def _update_async(self):
        assert iscoroutinefunction(self._update)
        await self._update()
        return True

    def _cleanup(self):
        pass


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


class ReactiveProxy(LazySwitchableProxy):
    def __init__(self, decorated: DecoratedFunction, args, kwargs):
        with ScopedName(name=decorated.callable.__name__):
            super().__init__(async=iscoroutinefunction(self._update))
        self.decorated = decorated  # type: DecoratedFunction

        # use dep_only_args
        for name in decorated.decorator.dep_only_args:
            if name in kwargs:
                arg = kwargs[name]  # fixme use "pop"

                if isinstance(arg, (list, tuple)):
                    for a in arg:
                        observe(a, self.__notifier__)
                else:
                    observe(arg, self.__notifier__)

                del kwargs[name]

        # use other_deps
        for dep in decorated.decorator.other_deps:
            maybe_observe(dep, self.__notifier__)

        self.args_helper = ArgsHelper(args, kwargs, decorated.signature, decorated.really_call)
        self.args = self.args_helper.args
        self.kwargs = self.args_helper.kwargs
        self._update_in_progress = False

        observe_args(self.args_helper, self.decorated.decorator.pass_args, self.__notifier__)

    @contextmanager
    def _handle_exception(self, reraise=True):
        try:
            yield

        except Exception as e:
            if isinstance(e, HideStackHelper):
                e = e.__cause__
            if isinstance(e, SilentError):
                e = e.__cause__
                reraise = False  # SilentError is not re-raised by definition
            self._exception = e
            if reraise:
                raise HideStackHelper() from e

    def _call(self):
        # returns one of:
        # - the result,
        # - a coroutine (to be awaited),
        # - a generator to be run once and finalized before the next call
        # - an async generator
        assert self._update_in_progress == False, 'circular dependency containing {}'.format(self.__notifier__.name)
        try:
            self._update_in_progress = True
            args, kwargs = rewrap_args(self.args_helper, self.decorated.decorator.pass_args, self.__notifier__.name)
            res = self.decorated.really_call(args, kwargs)
            self._update_in_progress = False
            return res
        except Exception:
            self._update_in_progress = False
            raise

    @abstractmethod
    def _update(self, retval=None):
        pass


class SyncReactiveProxy(ReactiveProxy):
    def _update(self, retval=None):
        with self._handle_exception(reraise=True):
            res = self._call()
            self._set_ref(res)
        return retval


class AsyncReactiveProxy(ReactiveProxy):
    async def _update(self, retval=None):
        with self._handle_exception(reraise=True):
            res = await self._call()
            self._set_ref(res)
        return retval


class CmReactiveProxy(ReactiveProxy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cm = None

    def _update(self, retval=None):
        self._cleanup()

        with self._handle_exception(reraise=True):
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

        with self._handle_exception(reraise=True):
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


def volatile(var):
    if var is not None:  # var may be none if we make "volatile(foo(x))" where foo is reactive and x is not observable
        return VolatileProxy(var)