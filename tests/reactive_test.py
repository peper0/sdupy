import asyncio
import gc

import asynctest

from sdupy.reactive import wait_for_var
from sdupy.reactive.common import WrapperInterface, unwrap, unwrap_exception
from sdupy.reactive.decorators import reactive, reactive_finalizable
# from sdupy.reactive.decorators import reactive, reactive_finalizable, var_from_gen
# from sdupy.reactive.var import Observable, var, Wrapper
from sdupy.reactive.notifier import Notifier
from sdupy.reactive.var import const, var


class NotifierTests(asynctest.TestCase):
    def setUp(self):
        self._notifier = Notifier()
        self._notifier2 = Notifier()
        self.cbk_called = 0

    def cbk(self):
        self.cbk_called += 1

    async def test_first(self):
        cbk = self.cbk
        self._notifier.add_observer(cbk, None)
        await asyncio.sleep(0.1)
        self.assertEqual(self.cbk_called, 0)

        self._notifier.notify_observers()

        await asyncio.sleep(0.1)
        self.assertEqual(self.cbk_called, 1)

    async def test_dont_call_multiple(self):
        cbk = self.cbk
        self._notifier.add_observer(cbk, None)
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
        self.assertIsInstance(res, WrapperInterface)
        self.assertEqual(unwrap(res), 7)

    async def test_var_val_keyword(self):
        a = var(2)
        res = my_sum(a=a, b=5)
        await wait_for_var(res)
        self.assertIsInstance(res, WrapperInterface)
        self.assertEqual(unwrap(res), 7)

    async def test_var_var(self):
        a = var(2)
        b = var(5)
        res = my_sum(a=a, b=b)
        await wait_for_var(res)
        self.assertIsInstance(res, WrapperInterface)
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
        self.assertIsInstance(res, WrapperInterface)
        self.assertEqual(unwrap(res), 7)

    async def test_var_val_keyword(self):
        a = var(2)
        res = await async_sum(a=a, b=5)
        self.assertIsInstance(res, WrapperInterface)
        self.assertEqual(unwrap(res), 7)

    async def test_var_var(self):
        a = var(2)
        b = var(5)
        res = await async_sum(a=a, b=b)
        self.assertIsInstance(res, WrapperInterface)
        self.assertEqual(unwrap(res), 7)

    async def test_var_changes(self):
        a = var(2)
        b = var(5)
        res = await async_sum(a=a, b=b)
        a.set(6)
        await wait_for_var(res)
        self.assertEqual(unwrap(res), 11)  # 6+5
        b.set(3)
        await wait_for_var(res)
        self.assertEqual(unwrap(res), 9)  # 6+3

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

    async def test_a(self):
        b = var(5)
        res = sum_with_yield(2, b=b)
        self.assertIsInstance(res, WrapperInterface)
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
        self.assertIsInstance(res, WrapperInterface)
        await wait_for_var(res)
        gc.collect()
        self.assertEqual(inside, 0)
        self.assertIsNotNone(unwrap_exception(res))
        with self.assertRaisesRegex(Exception, r'.*b.*'):
            unwrap(res)
        b.set(5)
        await wait_for_var(res)
        gc.collect()
        self.assertEqual(inside, 1)
        self.assertIsNone(unwrap_exception(res))
        self.assertEqual(unwrap(res), 7)


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
        self.assertIsInstance(res, WrapperInterface)
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
        res = await async_sum_with_yield(2, b=b)  # type: WrapperInterface
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


class Forwarders(asynctest.TestCase):
    async def test_operator_add(self):
        a = var(2)
        b = const(5)
        res = a + b
        self.assertEqual(unwrap(res), 7)

        a @= 6
        await wait_for_var(res)
        self.assertEqual(unwrap(res), 11)  # 6+5

    async def test_operator_cmp(self):
        a = var(2)
        b = var(5)
        a_greater = a > b
        self.assertFalse(unwrap(a_greater))

        a @= 5
        await wait_for_var()
        self.assertFalse(unwrap(a_greater))

        a @= 6
        await wait_for_var()
        self.assertTrue(unwrap(a_greater))


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
        self.assertEqual(called_times, 1)

        a @= 55
        await wait_for_var(res)
        await asyncio.sleep(0.1)
        self.assertEqual(called_times, 2)

        some_observable.__notifier__.notify_observers()
        await wait_for_var(res)
        await asyncio.sleep(1)
        self.assertEqual(called_times, 3)

        some_observable.__notifier__.notify_observers()
        await wait_for_var(res)
        await asyncio.sleep(1)
        self.assertEqual(called_times, 4)


called_times2 = 0


@reactive(dep_only_args=['ignored_arg'])
def inc_called_times2(a):
    global called_times2
    called_times2 += 1
    return a


class DepOnlyArgs(asynctest.TestCase):
    async def test_vars(self):
        global called_times2
        called_times2 = 0
        a = var(55)
        res = inc_called_times2(a, ignored_arg=some_observable)
        await wait_for_var(res)
        self.assertEqual(called_times2, 1)
        self.assertEqual(res, 55)

        a @= 10
        await wait_for_var(res)
        self.assertEqual(called_times2, 2)
        self.assertEqual(res, 10)

        some_observable.__notifier__.notify_observers()
        await wait_for_var(res)
        self.assertEqual(called_times2, 3)
        self.assertEqual(res, 10)


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

        self.assertIsInstance(res, WrapperInterface)
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
