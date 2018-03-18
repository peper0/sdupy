import asyncio
import inspect
from contextlib import contextmanager
from typing import Callable, Iterable, Union, overload

import asyncio_extras

from sdupy.reactive.common import CoroutineFunction, is_wrapper


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
            def factory(*args, **kwargs):
                # import here to avoid circular dependency (AsyncReactiveProxy does Reactive.__call__ for it's members)
                from .var import AsyncReactiveProxy
                return AsyncReactiveProxy(*args, **kwargs)
        elif hasattr(func, '__call__'):
            def factory(*args, **kwargs):
                from .var import SyncReactiveProxy
                return SyncReactiveProxy(*args, **kwargs)
        else:
            raise Exception("{} is neither a function nor a coroutine function (async def...)".format(repr(func)))
        return DecoratedFunction(self, factory, func)


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
        if args_need_reaction(args, kwargs):
            res = self.factory(self, args, kwargs)
            return res._update(res)
        else:
            return self.callable(*args, **kwargs)


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


class ReactiveCm(Reactive):
    def __call__(self, func):
        """
        Decorate the function.
        """
        if hasattr(func, '_isasync') and func._isasync:
            def factory(*args, **kwargs):
                # import here to avoid circular dependency (AsyncReactiveProxy does Reactive.__call__ for it's members)
                from .var import AsyncCmReactiveProxy
                return AsyncCmReactiveProxy(*args, **kwargs)
        elif hasattr(func, '__call__'):
            def factory(*args, **kwargs):
                from .var import CmReactiveProxy
                return CmReactiveProxy(*args, **kwargs)
        else:
            raise Exception("{} is neither a function nor a coroutine function (async def...)".format(repr(func)))
        return DecoratedFunction(self, factory, func)


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

            # noinspection PyTypeChecker
            return deco(ff)
        else:
            return deco(contextmanager(f))

    return wrap


def args_need_reaction(args: tuple, kwargs: dict):
    return any((is_wrapper(arg) for arg in args + tuple(kwargs.values())))
