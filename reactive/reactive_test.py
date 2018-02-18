import asyncio
import gc

import asynctest

from .reactive import reactive, reactive_finalizable, var_from_gen
from .var import VarBase, wait_for_var


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
    async def test_a(self):
        b = Var(5)
        res = sum_with_yield(2, b=b)
        self.assertIsInstance(res, VarBase)
        self.assertEqual(res.data, 7)
        self.assertEqual(inside, 1)
        b.set(1)
        print("w1")
        await wait_for_var(res)
        self.assertEqual(res.data, 3)
        self.assertEqual(inside, 1)
        # await res.dispose()
        del b
        gc.collect()
        print(gc.get_referrers(res))
        del res
        gc.collect()
        # await asyncio.sleep(1)
        self.assertEqual(inside, 0)
        print("finished)")


@reactive_finalizable()
async def async_sum_with_yield(a, b):
    global inside
    inside += 1
    yield a + b
    # cleanup
    inside -= 1


class AsyncReactiveWithYield(asynctest.TestCase):
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
        self.assertEqual(inside, 0)


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
