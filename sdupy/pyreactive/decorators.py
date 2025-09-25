import asyncio
import inspect
import contextlib
import functools
import logging
import traceback
from contextlib import suppress
from functools import wraps
from typing import Callable, Iterable, Union, overload

import asyncio_extras

from sdupy.pyreactive import settings
from sdupy.pyreactive.common import CoroutineFunction, is_wrapper


class HideStackHelper(Exception):
    def exception_to_rethrow(self):
        return self.__cause__.with_traceback(self.__cause__.__traceback__.tb_next.tb_next)


def hide_nested_calls(f: Callable):
    """
    When reporting an exception, hide nested calls from here up to stop_hiding_nested_calls()
    """
    if not settings.HIDE_IRREVELANT_STACK_FRAMES:
        return f
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except HideStackHelper as e:
            # the string below is to make it easier to analyze stack traces
            raise e.exception_to_rethrow() from None  # ----- IGNORE THIS FRAME -----

    return wrapper


def stop_hiding_nested_calls(f: Callable):
    """
    When reporting an exception, hide nested calls from here up to stop_hiding_nested_calls()
    """
    if not settings.HIDE_IRREVELANT_STACK_FRAMES:
        return f

    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            raise HideStackHelper() from e

    return wrapper


class Reactive:
    def __init__(self, pass_args, other_deps, dep_only_args):
        self.dep_only_args = dep_only_args
        self.other_deps = other_deps
        self.pass_args = set(pass_args)

    @hide_nested_calls
    def __call__(self, func):
        """
        Decorate the function.
        """
        if asyncio.iscoroutinefunction(func):
            def factory(decorated, args, kwargs):
                # import here to avoid circular dependency (AsyncReactiveProxy does Reactive.__call__ for it's members)
                from .var import AsyncReactiveProxy
                res = AsyncReactiveProxy(decorated, args, kwargs)
                if args_need_reaction(res.args, res.kwargs):
                    #return res._update(res)
                    return res
                else:
                    return decorated.really_call(args, kwargs)
        elif hasattr(func, '__call__'):
            def factory(decorated, args, kwargs):
                # import here to avoid circular dependency (SyncReactiveProxy does Reactive.__call__ for it's members)
                from .var import SyncReactiveProxy
                NUM_INTERNAL_FRAMES = 3 if settings.HIDE_IRREVELANT_STACK_FRAMES else 2  # number of frames on stack that are not relevant for user
                trace = traceback.extract_stack()[:-NUM_INTERNAL_FRAMES]
                res = SyncReactiveProxy(decorated, args, kwargs, trace)
                if args_need_reaction(res.args, res.kwargs):
                    #return res._update(res)
                    return res
                else:
                    return decorated.really_call(args, kwargs)
        else:
            raise Exception("{} is neither a function nor a coroutine function (async def...)".format(repr(func)))
        return DecoratedFunction(self, factory, func)


class DecoratedFunction:
    def __init__(self, decorator: Reactive, factory, func: Union[CoroutineFunction, Callable]):
        self.decorator = decorator
        self.factory = factory
        self.callable = func
        try:
            self.signature = inspect.signature(func)
        except ValueError:
            self.signature = None
        self.args_names = list(self.signature.parameters) if self.signature else None
        functools.update_wrapper(self, func)

    @stop_hiding_nested_calls
    def really_call(self, args, kwargs):
        return self.callable(*args, **kwargs)

    @hide_nested_calls
    def __call__(self, *args, **kwargs):
        """
        Bind arguments, call function once and schedule it to be called on any arguments change.
        """
        return self.factory(self, args, kwargs)

    def __get__(self, instance, instancetype):
        """
        Implement the descriptor protocol to make decorating instance method possible.
        """
        if instance is None:
            logging.error("instance is None")
        return functools.partial(self.__call__, instance)

    def __str__(self):
        return 'DecoratedFunction({})'.format(self.callable)



@overload
def reactive(f: Callable) -> Callable:
    pass


@overload
def reactive(pass_args: Iterable[str] = None,
             other_deps: Iterable[str] = None,
             dep_only_args: Iterable[str] = None) -> Callable:
    pass


def reactive(pass_args: Iterable[str] = None,
             other_deps: Iterable[str] = None,
             dep_only_args: Iterable[str] = None):
    if callable(pass_args):
        # a shortcut that allows simple @reactive instead of @reactive()
        return reactive()(pass_args)

    pass_args = set(pass_args or [])
    dep_only_args = set(dep_only_args or [])
    other_deps = other_deps or []

    return Reactive(pass_args=pass_args, other_deps=other_deps, dep_only_args=dep_only_args)


@overload
def reactive_finalizable(f: Callable) -> Callable:
    pass


@overload
def reactive_finalizable(pass_args: Iterable[str] = None,
                         other_deps: Iterable[str] = None,
                         dep_only_args: Iterable[str] = None) -> Callable:
    pass


class ReactiveCm(Reactive):
    @hide_nested_calls
    def __call__(self, func):
        """
        Decorate the function.
        """
        if hasattr(func, '_isasync') and func._isasync:
            def factory(decorated, args, kwargs):
                # import here to avoid circular dependency (AsyncReactiveProxy does Reactive.__call__ for it's members)
                from .var import AsyncCmReactiveProxy
                res = AsyncCmReactiveProxy(decorated, args, kwargs)
                return res._update(res)

        elif hasattr(func, '__call__'):
            def factory(decorated, args, kwargs):
                from .var import CmReactiveProxy
                NUM_INTERNAL_FRAMES = 2  # number of frames on stack that are not relevant for user
                trace = traceback.extract_stack()[:-NUM_INTERNAL_FRAMES]
                res = CmReactiveProxy(decorated, args, kwargs, trace)
                # return res._update(res)
                return res
        else:
            raise Exception("{} is neither a function nor a coroutine function (async def...)".format(repr(func)))
        return DecoratedFunction(self, factory, func)


def reactive_finalizable(pass_args: Iterable[str] = None,
                         other_deps: Iterable[str] = None,
                         dep_only_args: Iterable[str] = None,
                         ):
    if callable(pass_args):
        # a shortcut that allows simple @reactive instead of @reactive()
        return reactive_finalizable()(pass_args)

    pass_args = set(pass_args or [])
    dep_only_args = set(dep_only_args or [])
    other_deps = other_deps or []

    deco = ReactiveCm(pass_args, dep_only_args, other_deps)

    def wrap(f):
        if inspect.isasyncgenfunction(f):
            ff = asyncio_extras.async_contextmanager(f)
            ff._isasync = True

            # noinspection PyTypeChecker
            return deco(ff)
        else:
            return deco(contextlib.contextmanager(f))

    return wrap


def args_need_reaction(args: tuple, kwargs: dict):
    return any((is_wrapper(arg) for arg in args + tuple(kwargs.values())))


# class TaskReactor(ReactorBase):
#     def __init__(self, var, binding: Binding):
#         super().__init__(var, binding)
#         self._task = None  # type: asyncio.Task
#
#     async def cleanup(self):
#         if self._task:
#             await cancel_and_wait(self._task)
#             self._task = None
#
#     async def _task_loop(self):
#         async for res in self._binding():
#             self._result_var_weak().provide(res)
#
#     async def update(self):
#         await self.cleanup()
#         self._task = asyncio.ensure_future(self._task_loop())
#
#     async def build_result(self, var):
#         await self.update()
#         self._result_var_weak().on_dispose = self.cleanup
#         return var
#
#
# def with_state(state=None):
#     def wrapper(f):
#         async def wrapped_f(*args, **kwargs):
#             state_holder = state.copy()
#             return await f(state_holder, *args, **kwargs)
#
#         return wrapped_f
#
#     return wrapper
#
#
# async def cancel_and_wait(task):
#     task.cancel()
#     try:
#         await task
#     except asyncio.CancelledError:
#         pass
#
#
# def unroll_gen(gen_arg=0):
#     def wrapper(coro_fun):
#         async def wrapped_f(*args, **kwargs):
#             if isinstance(gen_arg, str):
#                 async for i in kwargs[gen_arg]:
#                     kwargs[gen_arg] = i
#                     yield await coro_fun(*args, **kwargs)
#             elif isinstance(gen_arg, int):
#                 args = list(args)
#                 async for i in args[gen_arg]:
#                     args[gen_arg] = i
#                     yield await coro_fun(*args, **kwargs)
#             else:
#                 assert False, "gen_arg must be an integer (for positional arguments) or a string (for keyword arguments)"
#
#         return wrapped_f
#
#     return wrapper


"""
def reactive_coro(f, result_as_arg, attributes=None):
    async def wrapped_f(*args, **kwargs):
        result = Var(None)
        if attributes:
            result.__dict__.update(**attributes)

        async def update_coro():
            args_unwrapped, kwargs_unwrapped = rewrap_args(args, kwargs)
            if result_as_arg:
                res = await f(result, *args_unwrapped, *kwargs_unwrapped)
                assert res is None, "result must be passed to the first argument, not returned"
            else:
                result.set(await f(*args_unwrapped, *kwargs_unwrapped))

        observe_many(args, kwargs, update_coro)

        await update_coro()
        return result

    return wrapped_f


def reactive_fun(f, result_as_arg, attributes=None):
    def wrapped_f(*args, **kwargs):
        result = Var(None)
        if attributes:
            result.__dict__.update(**attributes)

        def update():
            print("doing update")
            args_unwrapped, kwargs_unwrapped = rewrap_args(args, kwargs)
            if result_as_arg:
                res = f(result, *args_unwrapped, **kwargs_unwrapped)
                assert res is None, "result must be passed to the first argument, not returned"
            else:
                result.set(f(*args_unwrapped, **kwargs_unwrapped))

        async def update_coro():
            update()

        observe_many(args, kwargs, update_coro)
        update()
        return result

    return wrapped_f


def reactive(f):
    if asyncio.iscoroutinefunction(f):
        return reactive_coro(f, result_as_arg=False)
    else:
        return reactive_fun(f, result_as_arg=False)

def reactive_with_state(**kwargs):
    def wrap(f):
        if asyncio.iscoroutinefunction(f):
            return reactive_coro(f, result_as_arg=True, attributes=kwargs)
        else:
            return reactive_fun(f, result_as_arg=True, attributes=kwargs)
    return wrap

"""
