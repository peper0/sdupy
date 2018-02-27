import asyncio
import inspect
import logging
import weakref
from abc import abstractmethod
from contextlib import suppress
from typing import Any, AsyncGenerator, AsyncIterator, Callable, Coroutine, Generator, Iterator, Set, Union, overload

from .common import VarInterface, ensure_coro_func

var_factory = None

logger = logging.getLogger('reactive')


def args_need_reaction(args: tuple, kwargs: dict):
    return any((isinstance(arg, VarInterface) for arg in args + tuple(kwargs.values())))


def rewrap_args(args, kwargs: dict, args_as_vars=set()):
    def as_value(arg):
        if isinstance(arg, VarInterface):
            return arg.data
        else:
            return arg

    def as_var(arg):
        if isinstance(arg, VarInterface):
            return arg
        else:
            return var_factory(arg)

    def rewrap(key: Union[str, int], arg):
        if key in args_as_vars:
            return as_var(arg)
        else:
            return as_value(arg)

    args_rewrapped = [rewrap(num, arg) for num, arg in enumerate(args)]
    kwargs_rewrapped = {key: rewrap(key, arg) for key, arg in kwargs.items()}
    return args_rewrapped, kwargs_rewrapped


def maybe_observe(arg: Union[VarInterface, Any], update):
    if isinstance(arg, VarInterface):
        return arg.add_observer(update)


def observe_many(args, kwargs, update):
    for arg in args:
        maybe_observe(arg, update)
    for k, arg, in kwargs.items():
        maybe_observe(arg, update)


CoroFunction = Callable[[], Coroutine]


@overload
def reactive(f: Callable) -> Callable:
    pass


@overload
def reactive(args_as_vars: Set[str]) -> Callable:
    pass


def update_kwargs_with_defaults(func, args, kwargs):
    signature = inspect.signature(func)
    for i, (k, v) in enumerate(signature.parameters.items()):
        #print("arg", i, k, v, len(args))
        if i >= len(args) and v.default is not inspect.Parameter.empty and k not in kwargs:
            kwargs[k] = v.default
    return kwargs


def reactive(args_as_vars=set()):
    if callable(args_as_vars):
        # a shortcut that allows simple @reactive instead of @reactive()
        return reactive()(args_as_vars)

    def wrapper(f):
        if asyncio.iscoroutinefunction(f):
            factory = AsyncReactor
        elif hasattr(f, '__call__'):
            factory = Reactor
        else:
            raise Exception("{} is neither a function nor a coroutine function (async def...)".format(repr(f)))

        def wrapped(*args, **kwargs):
            #print("args0", args)
            #print("kwargs0", kwargs)
            kwargs = update_kwargs_with_defaults(f, args, kwargs)  # handle vars in default args
            #print("kwargs", kwargs)

            if args_need_reaction(args, kwargs):
                binding = Binding(f, args_as_vars=args_as_vars, args=args, kwargs=kwargs)
                var = var_factory()
                return factory(var, binding).build_result(var)
            else:
                return f(*args, **kwargs)

        return wrapped

    return wrapper


def reactive_finalizable(args_as_vars: Set[str]=set()):
    def wrapper(f):
        if inspect.isasyncgenfunction(f):
            factory = AsyncYieldingReactor
        elif inspect.isgeneratorfunction(f):
            factory = YieldingReactor
        else:
            raise Exception("{} is neither a generator function nor an async generator function; didn't you forget "
                            "using 'yield' inside?".format(repr(f)))

        def wrapped(*args, **kwargs):
            kwargs = update_kwargs_with_defaults(f, args, kwargs)  # handle vars in default args
            binding = Binding(f, args_as_vars=args_as_vars, args=args, kwargs=kwargs)
            var = var_factory()
            return factory(var, binding).build_result(var)

        return wrapped

    return wrapper


def reactive_task(args_as_vars=set()):
    def wrapper(f):
        if not (asyncio.iscoroutinefunction(f) or inspect.isasyncgenfunction(f)):
            raise Exception("{} is not a coroutine function (async def...)".format(repr(f)))

        def wrapped(*args, **kwargs):
            binding = Binding(f, args_as_vars, args, kwargs)
            var = var_factory()
            TaskReactor(var, binding).build_result(var)
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
    def __init__(self, var: VarInterface, binding: Binding):
        self._binding = binding
        self._result_var_weak = weakref.ref(var)
        update = self.update
        var.keep_reference(update)  # keep reference as long as "var" exists
        observe_many(self._binding.args, self._binding.kwargs, update)

    @abstractmethod
    def update(self):
        raise NotImplementedError

    @abstractmethod
    def build_result(self, var):
        raise NotImplementedError


class Reactor(ReactorBase):
    def update(self):
        self._result_var_weak().provide(self._binding())

    def build_result(self, var):
        self.update()
        return var


class AsyncReactor(ReactorBase):
    async def update(self):
        self._result_var_weak().provide(await self._binding())

    async def build_result(self, var):
        await self.update()
        return var


unfinished_iterators = set()


class YieldingReactor(ReactorBase):
    def __init__(self, var, binding: Binding):
        super().__init__(var, binding)
        self._iterator = None  # type: Iterator

    def cleanup(self):
        if self._iterator:
            with suppress(StopIteration):
                next(self._iterator)
                raise Exception("two yields in function %s")
            logger.debug('deleting reactor %s', self)
            unfinished_iterators.remove(self._iterator)
            self._iterator = None

    def update(self):
        self.cleanup()
        self._iterator = iter(self._binding())
        unfinished_iterators.add(self._iterator)
        self._result_var_weak().provide(next(self._iterator))

    def build_result(self, var):
        self.update()
        var.on_dispose = ensure_coro_func(self.cleanup)
        logger.debug('built reactor %s %s', self, self._iterator)
        return var


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
        self._result_var_weak().provide(await self._iterator.__anext__())

    async def build_result(self, var):
        await self.update()
        var.on_dispose = self.cleanup
        return var


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
            self._result_var_weak().provide(res)

    async def update(self):
        await self.cleanup()
        self._task = asyncio.ensure_future(self._task_loop())

    async def build_result(self, var):
        await self.update()
        self._result_var_weak().on_dispose = self.cleanup
        return var


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
