import asyncio
import inspect
import weakref
from abc import abstractmethod
from contextlib import suppress
from typing import Any, AsyncGenerator, AsyncIterator, Callable, Coroutine, Generator, Iterator, Union

from .var import Var, myprint


def args_need_reaction(args: tuple, kwargs: dict):
    return any((isinstance(arg, Var) for arg in args + tuple(kwargs.values())))


def rewrap_args(args, kwargs: dict, args_as_vars=set()):
    def as_value(arg):
        if isinstance(arg, Var):
            return arg.data
        else:
            return arg

    def as_var(arg):
        if isinstance(arg, Var):
            return arg
        else:
            return Var(arg)

    def rewrap(key: Union[str, int], arg):
        if key in args_as_vars:
            return as_var(arg)
        else:
            return as_value(arg)

    args_rewrapped = [rewrap(num, arg) for num, arg in enumerate(args)]
    kwargs_rewrapped = {key: rewrap(key, arg) for key, arg in kwargs.items()}
    return args_rewrapped, kwargs_rewrapped


def maybe_observe(arg: Union[Var, Any], update):
    if isinstance(arg, Var):
        return arg.add_observer(update)


def observe_many(args, kwargs, update):
    for arg in args:
        maybe_observe(arg, update)
    for k, arg, in kwargs.items():
        maybe_observe(arg, update)


def ensure_coro_func(f):
    if asyncio.iscoroutinefunction(f):
        return f
    elif hasattr(f, '__call__'):
        async def async_f(*args, **kwargs):
            return f(*args, **kwargs)

        return async_f


CoroFunction = Callable[[], Coroutine]


def reactive(args_as_vars=set()):
    def wrapper(f):

        if asyncio.iscoroutinefunction(f):
            factory = AsyncReactor
        elif hasattr(f, '__call__'):
            factory = Reactor
        else:
            raise Exception("{} is neither a function nor a coroutine function (async def...)".format(repr(f)))

        def wrapped(*args, **kwargs):
            if args_need_reaction(args, kwargs):
                binding = Binding(f, args_as_vars, args, kwargs)
                var = Var()
                factory(var, binding).build_result()
                return var
            else:
                return f(*args, **kwargs)

        return wrapped

    return wrapper


def reactive_finalizable(args_as_vars=set()):
    def wrapper(f):

        if inspect.isasyncgenfunction(f):
            factory = AsyncYieldingReactor
        elif hasattr(f, '__call__'):
            factory = YieldingReactor
        else:
            raise Exception("{} is neither a function nor a coroutine function (async def...)".format(repr(f)))

        def wrapped(*args, **kwargs):
#            if args_need_reaction(args, kwargs):
            binding = Binding(f, args_as_vars, args, kwargs)
            var = Var()
            factory(var, binding).build_result()
            return var
#            else:
#                return f(*args, **kwargs)

        return wrapped

    return wrapper


def reactive_task(args_as_vars=set()):
    def wrapper(f):
        if not (asyncio.iscoroutinefunction(f) or inspect.isasyncgenfunction(f)):
            raise Exception("{} is not a coroutine function (async def...)".format(repr(f)))

        def wrapped(*args, **kwargs):
            binding = Binding(f, args_as_vars, args, kwargs)
            var = Var()
            TaskReactor(var, binding).build_result()
            return var

        return wrapped

    return wrapper


@reactive_task()
async def var_from_gen(async_gen: AsyncGenerator):
    async for i in async_gen:
        yield i
        # fixme: some aclose somewhere?


class Binding:
    def __init__(self, func, args_as_vars, args, kwargs):
        self.func = func  # type: Callable[Any, Union[function, CoroFunction, Generator, AsyncGenerator]]
        self.args_as_vars = args_as_vars
        self.args = args
        self.kwargs = kwargs

    def __call__(self):
        args_rewrapped, kwargs_rewrapped = rewrap_args(self.args, self.kwargs, args_as_vars=self.args_as_vars)
        return self.func(*args_rewrapped, **kwargs_rewrapped)


class ReactorBase:
    def __init__(self, var: Var, binding: Binding):
        self._binding = binding
        self._result_var_weak = weakref.ref(var)
        update = ensure_coro_func(self.update)
        import sys
        #myprint("refcnt1 ", sys.getrefcount(update))
        var.keep_reference(update)  # keep reference as long as "var" exists
        #myprint("refcnt2 ", sys.getrefcount(update))
        observe_many(self._binding.args, self._binding.kwargs, update)
        #myprint("refcnt3 ", sys.getrefcount(update))
        #del update

    @abstractmethod
    def update(self):
        raise NotImplementedError

    @abstractmethod
    def build_result(self):
        raise NotImplementedError


class Reactor(ReactorBase):
    def update(self):
        self._result_var_weak().set(self._binding())

    def build_result(self):
        self.update()
        return self._result_var_weak()


class AsyncReactor(ReactorBase):
    async def update(self):
        self._result_var_weak().set(await self._binding())

    async def build_result(self):
        await self.update()


unfinished_iterators = set()


class YieldingReactor(ReactorBase):
    def __init__(self, var, binding: Binding):
        super().__init__(var, binding)
        self._iterator = None  # type: Iterator

    def cleanup(self):
        import os
        os.write(1, "cleanup{}{}\n".format(self, self._iterator).encode())
        if self._iterator:
            with suppress(StopIteration):
                os.write(1, "nexing{}{}\n".format(self._iterator.gi_running, self._iterator.gi_frame).encode())
                next(self._iterator)
                os.write(1, b"ehe\n")
                raise Exception("two yields in function %s")
            unfinished_iterators.remove(self._iterator)
            os.write(1, b"fin\n")
            self._iterator = None
        os.write(1, b"cleanup fin\n")

    def update(self):
        import os
        os.write(1, "update {} {}\n".format(self, self._iterator).encode())
        self.cleanup()
        self._iterator = iter(self._binding())
        unfinished_iterators.add(self._iterator)
        self._result_var_weak().set(next(self._iterator))
        import os
        os.write(1, "aaaanexing{} {}\n".format(self, self._iterator).encode())

    def build_result(self):
        self.update()
        import os
        self._result_var_weak().on_dispose = ensure_coro_func(self.cleanup)
        os.write(1, "new {} {}\n".format(self, self._iterator).encode())


class AsyncYieldingReactor(ReactorBase):
    def __init__(self, var, binding: Binding):
        super().__init__(var, binding)
        self._iterator = None  # type: AsyncIterator

    async def cleanup(self):
        if self._iterator:
            with suppress(StopAsyncIteration):
                await self._iterator.__anext__()
                raise Exception("two yields in function %s")
            self._iterator = None

    async def update(self):
        await self.cleanup()
        self._iterator = self._binding().__aiter__()
        self._result_var_weak().set(await self._iterator.__anext__())

    async def build_result(self):
        await self.update()
        self._result_var_weak().on_dispose = self.cleanup


class TaskReactor(ReactorBase):
    def __init__(self, var, binding: Binding):
        super().__init__(var, binding)
        self._task = None  # type: asyncio.Task

    async def cleanup(self):
        if self._task:
            await cancel_and_wait(self._task)
            self._task = None

    async def _task_loop(self):
        async for res in self._binding():
            self._result_var_weak().set(res)

    async def update(self):
        await self.cleanup()
        self._task = asyncio.ensure_future(self._task_loop())

    async def build_result(self):
        await self.update()
        self._result_var_weak().on_dispose = self.cleanup


def with_state(state=None):
    def wrapper(f):
        async def wrapped_f(*args, **kwargs):
            state_holder = state.copy()
            return await f(state_holder, *args, **kwargs)

        return wrapped_f

    return wrapper


async def cancel_and_wait(task):
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def unroll_gen(gen_arg=0):
    def wrapper(coro_fun):
        async def wrapped_f(*args, **kwargs):
            if isinstance(gen_arg, str):
                async for i in kwargs[gen_arg]:
                    kwargs[gen_arg] = i
                    yield await coro_fun(*args, **kwargs)
            elif isinstance(gen_arg, int):
                args = list(args)
                async for i in args[gen_arg]:
                    args[gen_arg] = i
                    yield await coro_fun(*args, **kwargs)
            else:
                assert False, "gen_arg must be an integer (for positional arguments) or a string (for keyword arguments)"

        return wrapped_f

    return wrapper


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

"""
============================ tests ================
"""
