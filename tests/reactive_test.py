import asyncio
import gc

import asynctest

from sdupy.pyreactive import wait_for_var
from sdupy.pyreactive.common import Wrapped, unwrap, unwrap_exception, unwrapped
from sdupy.pyreactive.decorators import reactive, reactive_finalizable
# from sdupy.reactive.decorators import reactive, reactive_finalizable, var_from_gen
# from sdupy.reactive.var import Observable, var, Wrapper
from sdupy.pyreactive.notifier import Notifier
from sdupy.pyreactive.var import var


class NotifierTests(asynctest.TestCase):
    def setUp(self):
        self._notifier = Notifier(lambda: True, 'notifier')
        self._notifier2 = Notifier(self.cbk, 'notifier2')
        self.cbk_called = 0

    def cbk(self):
        self.cbk_called += 1
        return False

    async def test_first(self):
        self._notifier.add_observer(self._notifier2)
        await asyncio.sleep(0.1)
        self.assertEqual(self.cbk_called, 0)

        self._notifier.notify_observers()

        await asyncio.sleep(0.1)
        self.assertEqual(self.cbk_called, 1)

    async def test_dont_call_multiple(self):
        self._notifier.add_observer(self._notifier2)
        await asyncio.sleep(0.1)
        self.assertEqual(self.cbk_called, 0)

        for i in range(10):
            self._notifier.notify_observers()

        await asyncio.sleep(0.1)
        self.assertEqual(self.cbk_called, 1)


@reactive
def my_sum(a, b):
    return a + b


class SimpleReactive(asynctest.TestCase):
    async def test_vals_positional(self):
        self.assertEqual(my_sum(2, 5), 7)

    async def test_vals_keyword(self):
        self.assertEqual(my_sum(a=2, b=5), 7)

    async def test_var_val_positional(self):
        a = var(2)
        res = my_sum(a, 5)
        await wait_for_var(res)
        self.assertIsInstance(res, Wrapped)
        self.assertEqual(unwrap(res), 7)

    async def test_var_val_keyword(self):
        a = var(2)
        res = my_sum(a=a, b=5)
        await wait_for_var(res)
        self.assertIsInstance(res, Wrapped)
        self.assertEqual(unwrap(res), 7)

    async def test_var_var(self):
        a = var(2)
        b = var(5)
        res = my_sum(a=a, b=b)
        await wait_for_var(res)
        self.assertIsInstance(res, Wrapped)
        self.assertEqual(unwrap(res), 7)

    async def test_var_changes(self):
        a = var(2)
        b = var(5)
        res = my_sum(a=a, b=b)
        a @= 6
        await wait_for_var(res)
        self.assertEqual(unwrap(res), 11)  # 6+5
        b @= 3
        await wait_for_var(res)
        self.assertEqual(unwrap(res), 9)  # 6+3

    async def test_exception_propagation(self):
        a = var(None)
        b = var()
        res = my_sum(a=a, b=b)
        await wait_for_var(res)
        self.assertIsNotNone(unwrap_exception(res))
        with self.assertRaisesRegex(Exception, r'.*b.*'):
            unwrap(res)


@reactive
async def async_sum(a, b):
    return a + b


class SimpleReactiveAsync(asynctest.TestCase):
    async def test_vals_positional(self):
        self.assertEqual(await async_sum(2, 5), 7)

    async def test_vals_keyword(self):
        self.assertEqual(await async_sum(a=2, b=5), 7)

    async def test_var_val_positional(self):
        a = var(2)
        res = await async_sum(a, 5)
        self.assertIsInstance(res, Wrapped)
        self.assertEqual(unwrap(res), 7)

    async def test_var_val_keyword(self):
        a = var(2)
        res = await async_sum(a=a, b=5)
        self.assertIsInstance(res, Wrapped)
        self.assertEqual(unwrap(res), 7)

    async def test_var_var(self):
        a = var(2)
        b = var(5)
        res = await async_sum(a=a, b=b)
        self.assertIsInstance(res, Wrapped)
        self.assertEqual(unwrap(res), 7)

    async def test_var_changes(self):
        a = var(2)
        b = var(5)
        res = await async_sum(a=a, b=b)
        a.set(6)
        await wait_for_var(res)
        self.assertEqual(11, unwrap(res))  # 6+5
        b.set(3)
        await wait_for_var(res)
        self.assertEqual(9, unwrap(res))  # 6+3

    async def test_exception_propagation(self):
        a = var(3)
        b = var()
        res = await async_sum(a=a, b=b)
        await wait_for_var(res)
        self.assertIsNotNone(unwrap_exception(res))
        with self.assertRaisesRegex(Exception, r'.*b.*'):
            unwrap(res)


inside = 0


@reactive_finalizable
def sum_with_yield(a, b):
    global inside
    inside += 1
    # do work and return the result
    yield a + b
    # cleanup
    inside -= 1


class ReactiveWithYield(asynctest.TestCase):
    async def setUp(self):
        gc.collect()
        await asyncio.sleep(0.01)
        self.assertEqual(inside, 0)

    async def tearDown(self):
        gc.collect()
        await asyncio.sleep(0.01)
        self.assertEqual(inside, 0)

    async def test_with_raw(self):
        res = sum_with_yield(2, 5)
        # in this case we must return something that finalizes the function when destroyed
        self.assertIsInstance(res, Wrapped)
        self.assertEqual(unwrap(res), 7)
        self.assertEqual(inside, 1)
        await wait_for_var(res)
        del res
        await wait_for_var()
        await asyncio.sleep(0.5)
        gc.collect()
        self.assertEqual(inside, 0)

    async def test_a(self):
        b = var(5)
        res = sum_with_yield(2, b=b)
        self.assertIsInstance(res, Wrapped)
        self.assertEqual(unwrap(res), 7)
        gc.collect()
        self.assertEqual(inside, 1)
        b.set(1)
        print("w1")
        await wait_for_var(res)
        self.assertEqual(unwrap(res), 3)
        self.assertEqual(inside, 1)
        # await res.dispose()
        del b
        gc.collect()
        # weak_res = weakref.ref(res)
        # print(gc.get_referrers(res))
        del res
        gc.collect()
        await wait_for_var()
        await asyncio.sleep(0.5)
        self.assertEqual(inside, 0)
        print("finished)")

    async def test_exception_propagation(self):
        b = var()
        res = sum_with_yield(2, b=b)
        self.assertIsInstance(res, Wrapped)
        await wait_for_var(res)
        gc.collect()
        self.assertIsNotNone(unwrap_exception(res))
        self.assertEqual(0, inside)
        with self.assertRaisesRegex(Exception, r'.*b.*'):
            unwrap(res)
        b.set(5)
        await wait_for_var(res)
        await asyncio.sleep(0.1)
        gc.collect()
        self.assertIsNone(unwrap_exception(res))
        self.assertEqual(7, unwrap(res))
        self.assertEqual(1, inside)


@reactive_finalizable
async def async_sum_with_yield(a, b):
    global inside
    inside += 1
    yield a + b
    # cleanup
    inside -= 1


class AsyncReactiveWithYield(asynctest.TestCase):
    async def setUp(self):
        gc.collect()
        await asyncio.sleep(0.01)
        self.assertEqual(inside, 0)

    async def tearDown(self):
        gc.collect()
        await asyncio.sleep(0.01)
        self.assertEqual(inside, 0)

    async def test_a(self):
        b = var(5)
        res = await async_sum_with_yield(2, b=b)
        self.assertIsInstance(res, Wrapped)
        self.assertEqual(unwrap(res), 7)
        self.assertEqual(inside, 1)
        b @= 1
        await wait_for_var(res)
        self.assertEqual(unwrap(res), 3)
        self.assertEqual(inside, 1)
        del res
        await asyncio.sleep((0.1))

    async def test_exception_propagation(self):
        b = var()
        res = await async_sum_with_yield(2, b=b)  # type: Wrapped
        await wait_for_var(res)
        self.assertEqual(inside, 0)
        self.assertIsNotNone(unwrap_exception(res))
        with self.assertRaisesRegex(Exception, r'.*b.*'):
            unwrap(res)

        b @= 5
        await wait_for_var(res)
        # self.assertEqual(inside, 1)
        # self.assertIsNone(res.exception)
        # self.assertEqual(raw(res), 7)


# class Builtin(asynctest.TestCase):
#     async def test_vars(self):
#         a = var([1, 2])
#         l = reactive(len)(a)
#         self.assertEqual(unwrap(l), 2)
#
#         a @= [3]
#         await wait_for_var(l)
#         self.assertEqual(unwrap(l), 1)


# @reactive(args_fwd_none=['a', 'b'])
# def none_proof_sum(a, b):
#     return a + b
#
#
# class SimpleReactiveBypassed(asynctest.TestCase):
#     async def test_vals(self):
#         self.assertEqual(none_proof_sum(2, 5), 7)
#         self.assertIsNone(none_proof_sum(2, None))
#         self.assertIsNone(none_proof_sum(None, 5))
#
#     async def test_vars(self):
#         a = var(None)
#         b = var(None)
#         res = none_proof_sum(a, b)
#         await wait_for_var(res)
#         self.assertIsNone(raw(res))
#         b.set(2)
#         await wait_for_var(res)
#         self.assertIsNone(raw(res))
#         a.set(3)
#         await wait_for_var(res)
#         self.assertEqual(raw(res), 5)


called_times = 0
some_observable = var()
some_observable2 = var()


@reactive(other_deps=[some_observable])
def inc_called_times(a):
    global called_times
    called_times += 1
    return a


class OtherDeps(asynctest.TestCase):
    async def test_vars(self):
        global called_times
        called_times = 0
        a = var(None)
        res = inc_called_times(a)
        await wait_for_var(res)
        unwrap(res)
        self.assertEqual(1, called_times)

        a @= 55
        await wait_for_var(res)
        await asyncio.sleep(0.1)
        unwrap(res)
        self.assertEqual(2, called_times)

        some_observable.__notifier__.notify_observers()
        await wait_for_var(res)
        await asyncio.sleep(1)
        unwrap(res)
        self.assertEqual(3, called_times)

        some_observable.__notifier__.notify_observers()
        await wait_for_var(res)
        await asyncio.sleep(1)
        unwrap(res)
        self.assertEqual(4, called_times)


called_times2 = 0


@reactive(dep_only_args=['ignored_arg'])
def inc_called_times2(a):
    global called_times2
    called_times2 += 1
    return a


class DepOnlyArgs(asynctest.TestCase):
    async def setUp(self):
        self.observable1 = var()
        self.observable2 = var()

    async def test_vars(self):
        global called_times2
        called_times2 = 0
        a = var(55)
        res = inc_called_times2(a, ignored_arg=self.observable1)
        await wait_for_var(res)
        self.assertEqual(55, res)
        self.assertEqual(1, called_times2)

        a @= 10
        await wait_for_var(res)
        self.assertEqual(10, res)
        self.assertEqual(2, called_times2)

        self.observable1.__notifier__.notify_observers()
        await wait_for_var(res)
        self.assertEqual(10, res)
        self.assertEqual(3, called_times2)

    async def test_iterable(self):
        global called_times2
        called_times2 = 0
        a = var(55)
        res = inc_called_times2(a, ignored_arg=[self.observable1, self.observable2])
        await wait_for_var(res)
        self.assertEqual(55, res)
        self.assertEqual(1, called_times2)

        self.observable1.__notifier__.notify_observers()
        await wait_for_var(res)
        self.assertEqual(55, res)
        self.assertEqual(2, called_times2)

        self.observable2.__notifier__.notify_observers()
        await wait_for_var(res)
        self.assertEqual(55, res)
        self.assertEqual(3, called_times2)


@reactive
def func_with_default(a, param_with_default=some_observable):
    global called_times2
    called_times2 += 1
    return a + param_with_default


class DefaultArgs(asynctest.TestCase):
    async def setUp(self):
        global called_times2
        global some_observable
        self.var1 = var()
        some_observable @= 3
        await wait_for_var()
        called_times2 = 0

    async def test_with_const_arg(self):
        global some_observable
        res = func_with_default(5)
        self.assertTrue(isinstance(res, Wrapped))
        await wait_for_var(res)
        self.assertEqual(1, called_times2)
        self.assertEqual(8, unwrap(res))
        some_observable @= 100
        await wait_for_var(res)
        unwrap(res)
        self.assertEqual(2, called_times2)
        self.assertEqual(105, unwrap(res))

    async def test_with_const_default_arg(self):
        global some_observable
        res = func_with_default(5, param_with_default=6)
        self.assertTrue(isinstance(res, int))
        await wait_for_var(res)
        self.assertEqual(called_times2, 1)
        some_observable @= 999
        await wait_for_var(res)
        self.assertEqual(called_times2, 1)


@reactive(pass_args=['a'])
def pass_args(a, b):
    global called_times2
    called_times2 += 1
    return unwrapped(a) + b


class PassArgs(asynctest.TestCase):
    async def setUp(self):
        global called_times2
        await wait_for_var()
        called_times2 = 0

    async def test_1(self):
        global some_observable
        a = var(5)
        b = var(3)
        res = pass_args(a, b)
        self.assertTrue(isinstance(res, Wrapped))
        await wait_for_var(res)
        self.assertEqual(8, unwrap(res))
        self.assertEqual(1, called_times2)
        a @= 10
        await wait_for_var(res)
        self.assertEqual(8, unwrap(res))
        self.assertEqual(1, called_times2)
        b @= 100
        await wait_for_var(res)
        self.assertEqual(110, unwrap(res))
        self.assertEqual(2, called_times2)


# ====================================================================

@reactive
async def appender(queue: asyncio.Queue):
    global inside
    inside += 1
    l = []
    try:
        while True:
            yield l
            l.append(await queue.get())
    finally:
        inside -= 1


class Task(asynctest.TestCase):
    async def setUp(self):
        global inside
        inside = 0

    @asynctest.skip("reactive_task is not maintained currently (but will be, hopefully)")
    async def test_a(self):
        queue = asyncio.Queue()
        res = await var_from_gen(appender(queue))

        self.assertIsInstance(res, Wrapped)
        await asyncio.sleep(0)
        self.assertEqual(unwrap(res), [])
        await queue.put(5)
        await asyncio.sleep(0.1)
        self.assertEqual(unwrap(res), [5])
        await queue.put(1)
        await asyncio.sleep(0)
        self.assertEqual(unwrap(res), [5, 1])
        self.assertEqual(inside, 1)
        await res.dispose()
        del res
        self.assertEqual(inside, 0)
