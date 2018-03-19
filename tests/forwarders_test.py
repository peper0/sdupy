import asynctest
from numpy.testing import assert_array_equal

from sdupy.reactive import const, unwrap, var, wait_for_var
from sdupy.reactive.var import ArgumentError


class Forwarders(asynctest.TestCase):
    async def test_operator_add(self):
        a = var(2)
        b = const(5)
        res = a + b
        self.assertEqual(unwrap(res), 7)

        a @= 6
        await wait_for_var(res)
        self.assertEqual(unwrap(res), 11)  # 6+5

    async def test_operator_mul_numpy(self):
        import numpy as np
        a = var(2)
        b = np.array([1, 2])
        res = a * b
        assert_array_equal(unwrap(res), np.array([2, 4]))

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

    async def test_operator_neg(self):
        a = var(2)
        res = -a
        self.assertEqual(unwrap(res), -2)

        a @= -5
        await wait_for_var()
        self.assertEqual(unwrap(res), 5)

    async def test_operator_assign_add(self):
        a = var(2)
        res = a + 5
        self.assertEqual(unwrap(res), 7)

        a += 3
        await wait_for_var()
        self.assertEqual(unwrap(a), 5)
        self.assertEqual(unwrap(res), 10)

    async def test_operator_getitem_and_exception(self):
        a = var(('a', 'b'))
        res = a[1]
        self.assertEqual(unwrap(res), 'b')

        a @= ('A', 'B', 'C')
        await wait_for_var()
        self.assertEqual(unwrap(res), 'B')

        a @= ('A',)
        await wait_for_var()
        with self.assertRaises(IndexError):
            unwrap(res)

        a @= 5
        await wait_for_var()
        with self.assertRaises(Exception):
            unwrap(res)

        # check if it works again
        a @= (1, 2, 3)
        await wait_for_var()
        self.assertEqual(unwrap(res), 2)

    async def test_operator_getitem_setitem_delitem(self):
        a = var()
        res = a[1]
        await wait_for_var()
        with self.assertRaises(ArgumentError):
            unwrap(res)

        a @= [1, 2, 3]
        await wait_for_var()
        self.assertEqual(unwrap(res), 2)

        a[1] = 'hej'
        await wait_for_var()
        self.assertEqual(unwrap(res), 'hej')

        del a[1]
        await wait_for_var()
        self.assertEqual(unwrap(res), 3)

    async def test_operator_var_index(self):
        a = var()
        b = var()
        res = a[b]

        b @= 2
        a @= [1, 2, 3]
        await wait_for_var()
        self.assertEqual(unwrap(res), 3)

        b @= 0
        await wait_for_var()
        self.assertEqual(unwrap(res), 1)
