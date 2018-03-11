import asyncio
import gc

import asynctest

from sdupy.reactive.decorators import reactive, reactive_finalizable, var_from_gen
from sdupy.reactive.var import Observable, Var, VarBase, wait_for_var


@reactive()
def my_sum(a, b):
    return a + b


class SimpleReactive(asynctest.TestCase):
    async def test_vals_positional(self):
        self.assertEqual(my_sum(2, 5), 7)

    async def test_vals_keyword(self):
        self.assertEqual(my_sum(a=2, b=5), 7)

    async def test_var_val_positional(self):
        a = Var(2)
        res = my_sum(a, 5)
        await wait_for_var(res)
        self.assertIsInstance(res, VarBase)
        self.assertEqual(res.data, 7)

    async def test_var_val_keyword(self):
        a = Var(2)
        res = my_sum(a=a, b=5)
        await wait_for_var(res)
        self.assertIsInstance(res, VarBase)
        self.assertEqual(res.data, 7)

    async def test_var_var(self):
        a = Var(2)
        b = Var(5)
        res = my_sum(a=a, b=b)
        await wait_for_var(res)
        self.assertIsInstance(res, VarBase)
        self.assertEqual(res.data, 7)

    async def test_var_changes(self):
        a = Var(2)
        b = Var(5)
        res = my_sum(a=a, b=b)
        a.set(6)
        await wait_for_var(res)
        self.assertEqual(res.data, 11)  # 6+5
        b.set(3)
        await wait_for_var(res)
        self.assertEqual(res.data, 9)  # 6+3

    async def test_exception_propagation(self):
        a = Var(None)
        b = Var()
        res = my_sum(a=a, b=b)
        await wait_for_var(res)
        self.assertIsNotNone(res.exception())
        with self.assertRaisesRegex(Exception, r'.*b.*'):
            res.data


@reactive()
async def async_sum(a, b):
    return a + b


class SimpleReactiveAsync(asynctest.TestCase):
    async def test_vals_positional(self):
        self.assertEqual(await async_sum(2, 5), 7)

    async def test_vals_keyword(self):
        self.assertEqual(await async_sum(a=2, b=5), 7)

    async def test_var_val_positional(self):
        a = Var(2)
        res = await async_sum(a, 5)
        self.assertIsInstance(res, VarBase)
        self.assertEqual(res.data, 7)

    async def test_var_val_keyword(self):
        a = Var(2)
        res = await async_sum(a=a, b=5)
        self.assertIsInstance(res, VarBase)
        self.assertEqual(res.data, 7)

    async def test_var_var(self):
        a = Var(2)
        b = Var(5)
        res = await async_sum(a=a, b=b)
        self.assertIsInstance(res, VarBase)
        self.assertEqual(res.data, 7)

    async def test_var_changes(self):
        a = Var(2)
        b = Var(5)
        res = await async_sum(a=a, b=b)
        a.set(6)
        await wait_for_var(res)
        self.assertEqual(res.data, 11)  # 6+5
        b.set(3)
        await wait_for_var(res)
        self.assertEqual(res.data, 9)  # 6+3

    async def test_exception_propagation(self):
        a = Var(3)
        b = Var()
        res = await async_sum(a=a, b=b)
        await wait_for_var(res)
        self.assertIsNotNone(res.exception())
        with self.assertRaisesRegex(Exception, r'.*b.*'):
            res.data


inside = 0


@reactive_finalizable()
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
        b = Var(5)
        res = sum_with_yield(2, b=b)
        self.assertIsInstance(res, VarBase)
        self.assertEqual(res.data, 7)
        gc.collect()
        self.assertEqual(inside, 1)
        b.set(1)
        print("w1")
        await wait_for_var(res)
        self.assertEqual(res.data, 3)
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
        b = Var()
        res = sum_with_yield(2, b=b)  # type: sdupy.reactive.RVal
        await wait_for_var(res)
        gc.collect()
        self.assertEqual(inside, 0)
        self.assertIsNotNone(res.exception())
        with self.assertRaisesRegex(Exception, r'.*b.*'):
            res.data
        b.set(5)
        await wait_for_var(res)
        gc.collect()
        self.assertEqual(inside, 1)
        self.assertIsNone(res.exception())
        self.assertEqual(res.data, 7)


@reactive_finalizable()
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
        b = Var(5)
        res = await async_sum_with_yield(2, b=b)
        self.assertIsInstance(res, VarBase)
        self.assertEqual(res.data, 7)
        self.assertEqual(inside, 1)
        b.set(1)
        await wait_for_var(res)
        self.assertEqual(res.data, 3)
        self.assertEqual(inside, 1)
        await res.dispose()
        del res

    async def test_exception_propagation(self):
        b = Var()
        res = await async_sum_with_yield(2, b=b)  # type: sdupy.reactive.RVal
        await wait_for_var(res)
        self.assertEqual(inside, 0)
        self.assertIsNotNone(res.exception())
        with self.assertRaisesRegex(Exception, r'.*b.*'):
            res.data

        b.set(5)
        await wait_for_var(res)
        # self.assertEqual(inside, 1)
        # self.assertIsNone(res.exception())
        # self.assertEqual(res.data, 7)


@reactive(args_fwd_none=['a', 'b'])
def none_proof_sum(a, b):
    return a + b


class SimpleReactiveBypassed(asynctest.TestCase):
    async def test_vals(self):
        self.assertEqual(none_proof_sum(2, 5), 7)
        self.assertIsNone(none_proof_sum(2, None))
        self.assertIsNone(none_proof_sum(None, 5))

    async def test_vars(self):
        a = Var(None)
        b = Var(None)
        res = none_proof_sum(a, b)
        await wait_for_var(res)
        self.assertIsNone(res.data)
        b.set(2)
        await wait_for_var(res)
        self.assertIsNone(res.data)
        a.set(3)
        await wait_for_var(res)
        self.assertEqual(res.data, 5)


called_times = 0
some_observable = Observable()


@reactive(other_deps=[some_observable])
def inc_called_times(a):
    global called_times
    called_times += 1
    return a


class OtherDeps(asynctest.TestCase):
    async def test_vars(self):
        global called_times
        called_times = 0
        a = Var(None)
        res = inc_called_times(a)
        await wait_for_var(res)
        self.assertEqual(called_times, 1)

        a.set(55)
        await wait_for_var(res)
        await asyncio.sleep(0.1)
        self.assertEqual(called_times, 2)

        some_observable.notify_observers()
        await wait_for_var(res)
        await asyncio.sleep(1)
        self.assertEqual(called_times, 3)

        some_observable.notify_observers()
        await wait_for_var(res)
        await asyncio.sleep(1)
        self.assertEqual(called_times, 4)


@reactive(dep_only_args=['ignored_arg'])
def inc_called_times2(a):
    global called_times2
    called_times2 += 1
    return a


class DepOnlyArgs(asynctest.TestCase):
    async def test_vars(self):
        global called_times2
        called_times2 = 0
        a = Var(55)
        res = inc_called_times2(a, ignored_arg=some_observable)
        await wait_for_var(res)
        self.assertEqual(called_times2, 1)
        self.assertEqual(res, 55)

        a.set(10)
        await wait_for_var(res)
        self.assertEqual(called_times2, 2)
        self.assertEqual(res, 10)

        some_observable.notify_observers()
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

        self.assertIsInstance(res, VarBase)
        await asyncio.sleep(0)
        self.assertEqual(res.data, [])
        await queue.put(5)
        await asyncio.sleep(0.1)
        self.assertEqual(res.data, [5])
        await queue.put(1)
        await asyncio.sleep(0)
        self.assertEqual(res.data, [5, 1])
        self.assertEqual(inside, 1)
        await res.dispose()
        del res
        self.assertEqual(inside, 0)
