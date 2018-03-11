import asyncio
import inspect
import logging
import weakref
from abc import abstractmethod
from contextlib import suppress
from typing import Any, AsyncGenerator, AsyncIterator, Callable, Coroutine, Generator, Iterable, Iterator, Set, Union, \
    overload

from .common import VarInterface, ensure_coro_func

var_factory = None

logger = logging.getLogger('reactive')


def args_need_reaction(args: tuple, kwargs: dict):
    return any((isinstance(arg, VarInterface) for arg in args + tuple(kwargs.values())))


def rewrap_args(args, kwargs: dict, args_as_vars=set(), ignore_args=set()):
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
        try:
            if key in args_as_vars:
                return as_var(arg)
            else:
                return as_value(arg)
        except Exception as exception:
            raise Exception("propagating exception from arg '{}'".format(key)) from exception

    args_rewrapped = [rewrap(num, arg) for num, arg in enumerate(args)]
    kwargs_rewrapped = {key: rewrap(key, arg) for key, arg in kwargs.items() if key not in ignore_args}
    return args_rewrapped, kwargs_rewrapped


def maybe_observe(arg: Union[VarInterface, Any], update):
    if isinstance(arg, VarInterface):
        return arg.add_observer(update)


def observe_many(args, kwargs, other_observables, update):
    for arg in args:
        maybe_observe(arg, update)
    for k, arg, in kwargs.items():
        maybe_observe(arg, update)
    for observable in other_observables:
        observable.add_observer(update)


CoroFunction = Callable[[], Coroutine]


@overload
def reactive(f: Callable) -> Callable:
    pass


@overload
def reactive(args_as_vars: Set[str]) -> Callable:
    pass


def update_kwargs_with_defaults(func, args, kwargs):
    try:
        signature = inspect.signature(func)
    except ValueError:  # we get this error when trying to get signature of builtins
        signature = None
    if signature:  # when no signature, simply ignore default arguments
        for i, (k, v) in enumerate(signature.parameters.items()):
            if i >= len(args) and v.default is not inspect.Parameter.empty and k not in kwargs:
                kwargs[k] = v.default
    return kwargs


class FuncSigHelper:
    def __init__(self, func):
        self.func = func
        try:
            Param = inspect.Parameter
            self.signature = inspect.signature(func)
            self.pos_to_keyword = [p.name for p in self.signature.parameters.values()
                                   if p.kind == Param.POSITIONAL_OR_KEYWORD]
            self.keyword_to_pos = {p.name: i for i, p in enumerate(self.signature.parameters.values())
                                   if p.kind == Param.POSITIONAL_OR_KEYWORD}
            self.pos_defaults = {p.name: p.default for p in self.signature.parameters.values()
                                 if (p.default is Param.empty) and
                                 p.kind in [Param.POSITIONAL_OR_KEYWORD, Param.POSITIONAL_ONLY]}
            self.keyword_defaults = {p.name: p.default for p in self.signature.parameters.values()
                                     if p.default is Param.empty and
                                     p.kind in [Param.POSITIONAL_OR_KEYWORD, Param.KEYWORD_ONLY]}
        except ValueError:  # we get this error when trying to get signature of builtins
            self.signature = None

    def get_arg(self, arg_name_or_index, args, kwargs):
        if isinstance(arg_name_or_index, str):
            pos = self.keyword_to_pos.get(arg_name_or_index)
            if pos is not None and pos < len(args):
                return args[pos]
            elif arg_name_or_index in kwargs:
                return kwargs.get(arg_name_or_index)
            else:
                return self.keyword_defaults[arg_name_or_index]

        elif isinstance(arg_name_or_index, int):
            if arg_name_or_index is not None and arg_name_or_index < len(args):
                return args[arg_name_or_index]
            elif self.pos_to_keyword[arg_name_or_index] in kwargs:
                return kwargs.get(self.pos_to_keyword[arg_name_or_index])
            else:
                return self.pos_defaults[arg_name_or_index]
        else:
            raise Exception('arg_name_or_index is neither str nor an int: {}'.format(arg_name_or_index))

    def args_not_none(self, args_to_check, args, kwargs):
        return all(self.get_arg(arg, args, kwargs) is not None for arg in args_to_check)

    def remove_vars(self, args_to_remove, args, kwargs):
        for arg in args_to_remove:
            if arg in kwargs:
                del kwargs[args]


def reactive(args_as_vars=set(), args_fwd_none=[], other_deps=[], dep_only_args=[]):
    if callable(args_as_vars):
        # a shortcut that allows simple @reactive instead of @reactive()
        return reactive()(args_as_vars)

    args_as_vars = set(args_as_vars)
    dep_only_args = set(dep_only_args)

    def wrapper(f):
        if asyncio.iscoroutinefunction(f):
            factory = AsyncReactor
        elif hasattr(f, '__call__'):
            factory = Reactor
        else:
            raise Exception("{} is neither a function nor a coroutine function (async def...)".format(repr(f)))

        sig_helper = FuncSigHelper(f)

        def wrapped(*args, **kwargs):
            # print("args0", args)
            # print("kwargs0", kwargs)
            kwargs = update_kwargs_with_defaults(f, args, kwargs)  # handle vars in default args
            # print("kwargs", kwargs)

            if args_need_reaction(args, kwargs):
                binding = Binding(f, sig_helper=sig_helper, args_as_vars=args_as_vars, args_fwd_none=args_fwd_none,
                                  dep_only_args=dep_only_args, args=args, kwargs=kwargs)
                var = var_factory()
                return factory(var, binding, other_deps).build_result(var)
            else:
                return f(*args, **kwargs) if sig_helper.args_not_none(args_fwd_none, args, kwargs) else None

        return wrapped

    return wrapper


def reactive_finalizable(args_as_vars: Set[str] = set(), args_fwd_none=[], other_deps=[], dep_only_args=[]):
    if callable(args_as_vars):
        # a shortcut that allows simple @reactive_finalizable instead of @reactive_finalizable()
        return reactive_finalizable()(args_as_vars)

    def wrapper(f):
        if inspect.isasyncgenfunction(f):
            factory = AsyncYieldingReactor
        elif inspect.isgeneratorfunction(f):
            factory = YieldingReactor
        else:
            raise Exception("{} is neither a generator function nor an async generator function; didn't you forget "
                            "using 'yield' inside?".format(repr(f)))

        sig_helper = FuncSigHelper(f)

        def wrapped(*args, **kwargs):
            kwargs = update_kwargs_with_defaults(f, args, kwargs)  # handle vars in default args
            binding = Binding(f, sig_helper=sig_helper, args_as_vars=args_as_vars, args_fwd_none=args_fwd_none,
                              dep_only_args=dep_only_args, args=args, kwargs=kwargs)
            var = var_factory()
            return factory(var, binding, other_deps).build_result(var)

        return wrapped

    return wrapper


def reactive_task(args_as_vars=set(), other_deps=[]):
    def wrapper(f):
        if not (asyncio.iscoroutinefunction(f) or inspect.isasyncgenfunction(f)):
            raise Exception("{} is not a coroutine function (async def...)".format(repr(f)))

        def wrapped(*args, **kwargs):
            binding = Binding(f, args_as_vars, args, kwargs)
            var = var_factory()
            TaskReactor(var, binding, other_deps).build_result(var)
            return var

        return wrapped

    return wrapper


@reactive_task()
async def var_from_gen(async_gen: AsyncGenerator):
    async for i in async_gen:
        yield i
        # fixme: some aclose somewhere?


class Binding:
    def __init__(self, func, sig_helper: FuncSigHelper, args_as_vars, args_fwd_none, dep_only_args, args, kwargs):
        self.dep_only_args = dep_only_args
        self.func = func  # type: Callable[Any, Union[function, CoroFunction, Generator, AsyncGenerator]]
        self.args_fwd_none = args_fwd_none
        self.args_as_vars = args_as_vars
        self.args = args
        self.kwargs = kwargs
        self.sig_helper = sig_helper

    def __call__(self):
        args_rewrapped, kwargs_rewrapped = rewrap_args(self.args, self.kwargs, args_as_vars=self.args_as_vars,
                                                       ignore_args=self.dep_only_args)
        if self.sig_helper.args_not_none(self.args_fwd_none, args_rewrapped, kwargs_rewrapped):
            return self.func(*args_rewrapped, **kwargs_rewrapped)


class ReactorBase:
    def __init__(self, var: VarInterface, binding: Binding, other_deps: Iterable):
        self._binding = binding
        self._result_var_weak = weakref.ref(var)
        update = self.update
        var.keep_reference(update)  # keep reference as long as "var" exists
        observe_many(self._binding.args, self._binding.kwargs, other_deps, update)

    @abstractmethod
    def update(self):
        raise NotImplementedError

    @abstractmethod
    def build_result(self, var):
        raise NotImplementedError


class Reactor(ReactorBase):
    def update(self):
        with self._result_var_weak().handle_exception():
            self._result_var_weak().provide(self._binding())

    def build_result(self, var):
        self.update()
        return var


class AsyncReactor(ReactorBase):
    async def update(self):
        with self._result_var_weak().handle_exception():
            self._result_var_weak().provide(await self._binding())

    async def build_result(self, var):
        await self.update()
        return var


unfinished_iterators = set()


class YieldingReactor(ReactorBase):
    def __init__(self, var, binding: Binding, other_deps):
        super().__init__(var, binding, other_deps)
        self._iterator = None  # type: Iterator

    def cleanup(self):
        if self._iterator:
            with suppress(StopIteration):
                next(self._iterator)
                raise Exception("two yields in function {}".format(self._binding.func))
            logger.debug('deleting reactor')
            unfinished_iterators.remove(self._iterator)
            self._iterator = None

    def update(self):
        self.cleanup()
        with self._result_var_weak().handle_exception():
            self._iterator = iter(self._binding())
            unfinished_iterators.add(self._iterator)
            with suppress(StopIteration):  # it's acceptable that the iterator finishes here
                self._result_var_weak().provide(next(self._iterator))

    def build_result(self, var):
        self.update()
        var.on_dispose = ensure_coro_func(self.cleanup)
        logger.debug('built reactor %s %s', self, self._iterator)
        return var


class AsyncYieldingReactor(ReactorBase):
    def __init__(self, var, binding: Binding, other_deps):
        super().__init__(var, binding, other_deps)
        self._iterator = None  # type: AsyncIterator

    async def cleanup(self):
        if self._iterator:
            with suppress(StopAsyncIteration):
                await self._iterator.__anext__()
                raise Exception("two yields in function %s")
            unfinished_iterators.remove(self._iterator)
            self._iterator = None

    async def update(self):
        await self.cleanup()
        with self._result_var_weak().handle_exception():
            self._iterator = self._binding().__aiter__()
            unfinished_iterators.add(self._iterator)
            with suppress(StopAsyncIteration):  # it's acceptable that the iterator finishes here
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
