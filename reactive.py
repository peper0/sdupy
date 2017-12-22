import asyncio
from contextlib import suppress
from typing import NamedTuple, Any, Awaitable, Callable, Coroutine

import asynctest


class QueueItem(NamedTuple):
    priority: int
    id: Any
    awaitable: Awaitable

    def __lt__(self, other):
        return self.priority < other.priority


def rethrow(f):
    print("finished: %s" % f)
    if f.cancelled():
        print("task was canceled")
        return
    e = f.exception()
    if e:
        print("err: " , e.__class__, e)
        if isinstance(e, asyncio.CancelledError):
            print("task was canceled 2")
        else:
            raise e


class Refresher:
    def __init__(self):
        self.queue = asyncio.PriorityQueue()
        print("starting")
        self.task = None  # type: asyncio.Task

    def maybe_start_task(self):
        if not self.task or self.task.done():
            self.task = asyncio.ensure_future(self.run())  # type: asyncio.Task
            self.task.add_done_callback(rethrow)

    def add_coroutine(self, hash, coro):
        t = QueueItem(1, hash, coro)
        print("add ", t)
        self.queue.put_nowait(t)
        self.maybe_start_task()

    async def run(self):
        update_next = None

        with suppress(asyncio.QueueEmpty):  # it's ok - if the queue is empty we just exit
            while True:
                print("waiting")
                update = update_next if update_next else self.queue.get_nowait()
                print("upd: ", update)
                try:
                    update_next = self.queue.get_nowait()
                    if update_next.id == update.id:  # skip update if is same as next
                        continue
                except asyncio.QueueEmpty:
                    update_next = None

                print("calling")
                await update.awaitable

refresher = None


async def wait_for_var(var):
    # fixme: waiting only for certain level
    await refresher.task


def get_default_refresher():
    global refresher
    if not refresher:
        refresher = Refresher()

    return refresher


class Var:
    def __init__(self, data):
        self.data = data
        self.coro_functions = []
        self.on_dispose = None
        self.disposed = False

    def __del__(self):
        if not self.disposed and self.on_dispose:
            get_default_refresher().add_coroutine(self.on_dispose, self.on_dispose())
        #assert self.disposed, "Var.dispose was not called before destroying"


    def set(self, new_data):
        self.data = new_data
        for corof in self.coro_functions:
            get_default_refresher().add_coroutine(corof, corof())

    async def dispose(self):
        if not self.disposed:
            print("disposing?")
            if self.on_dispose:
                print("disposing")
                await self.on_dispose()
            self.disposed = True
            # def __getattr__(self, item):
            #    print("getattr %s"% item)
            # def __getattribute__(self, item):
            #    print("getattribute %s"% item)

            #@reactive
            #def __add__(x, y):
            #    return x + y


def args_need_reaction(args: tuple, kwargs: dict):
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

    def rewrap(key: str, arg):
        if key in args_as_vars:
            return as_var(arg)
        else:
            return as_value(arg)

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

    def rewrap(key: str, arg):
        if key in args_as_vars:
            return as_var(arg)
        else:
            return as_value(arg)

    args_rewrapped = [rewrap(num, arg) for num, arg in enumerate(args)]
    kwargs_rewrapped = {key: rewrap(key, arg) for key, arg in kwargs.items()}
    return args_rewrapped, kwargs_rewrapped


def observe(arg, update_coro):
    if isinstance(arg, Var):
        arg.coro_functions.append(update_coro)


def observe_many(args, kwargs, update_coro):
    for arg in args:
        observe(arg, update_coro)
    for k, arg, in kwargs.items():
        observe(arg, update_coro)


def reactive(args_as_vars=set(), yield_for_return=False):
    def wrapper(f):
        async def wrapped_f(*args, **kwargs):
            state = dict()

            async def cleanup():
                if 'last_gen' in state:
                    with suppress(StopAsyncIteration):
                        await state['last_gen'].__anext__()
                        assert False, "two yields in function %s" % f

            async def run_once():
                args_rewrapped, kwargs_rewrapped = rewrap_args(args, kwargs, args_as_vars=args_as_vars)
                if yield_for_return:
                    await cleanup()
                    state['last_gen'] = f(*args_rewrapped, **kwargs_rewrapped).__aiter__()
                    return await state['last_gen'].__anext__()
                else:
                    return await f(*args_rewrapped, **kwargs_rewrapped)

            if yield_for_return or args_need_reaction(args, kwargs):
                result_var = Var(None)

                if yield_for_return:
                    result_var.on_dispose = cleanup

                async def update_coro():
                    result_var.set(await run_once())

                observe_many(args, kwargs, update_coro)
                await update_coro()
                return result_var

            else:
                return await run_once()

        return wrapped_f
    return wrapper


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


def reactive_task():
    def wrapper(f):
        async def wrapped_f(*args, **kwargs):
            task = asyncio.ensure_future(f(*args, **kwargs))
            yield task
            cancel_and_wait(task)

        return reactive(yield_for_return=True)(wrapped_f)
    return wrapper


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


@reactive()
async def async_sum(a, b):
    return a+b


class SimpleReactiveAsync(asynctest.TestCase):

    async def test_vals_positional(self):
        self.assertEqual(await async_sum(2, 5), 7)

    async def test_vals_keyword(self):
        self.assertEqual(await async_sum(a=2, b=5), 7)

    async def test_var_val_positional(self):
        a=Var(2)
        res = await async_sum(a, 5)
        self.assertIsInstance(res, Var)
        self.assertEqual(res.data, 7)

    async def test_var_val_keyword(self):
        a=Var(2)
        res = await async_sum(a=a, b=5)
        self.assertIsInstance(res, Var)
        self.assertEqual(res.data, 7)

    async def test_var_var(self):
        a=Var(2)
        b=Var(5)
        res = await async_sum(a=a, b=b)
        self.assertIsInstance(res, Var)
        self.assertEqual(res.data, 7)

    async def test_var_changes(self):
        a=Var(2)
        b=Var(5)
        res = await async_sum(a=a, b=b)
        a.set(6)
        await wait_for_var(res)
        self.assertEqual(res.data, 11)  # 6+5
        b.set(3)
        await wait_for_var(res)
        self.assertEqual(res.data, 9)  # 6+3


inside = 0


@reactive(yield_for_return=True)
async def async_sum_with_yield(a, b):
    global inside
    inside += 1
    print("in")
    yield a+b
    print("out")
    inside -= 1


class ReactiveWithYield(asynctest.TestCase):
    async def test_a(self):
        b = Var(5)
        res = await async_sum_with_yield(2, b=b)
        self.assertIsInstance(res, Var)
        self.assertEqual(res.data, 7)
        self.assertEqual(inside, 1)
        b.set(1)
        print("w1")
        await wait_for_var(res)
        self.assertEqual(res.data, 3)
        self.assertEqual(inside, 1)
        await res.dispose()
        del res
        self.assertEqual(inside, 0)
        print("finished)")
