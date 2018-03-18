import operator
from abc import abstractmethod
from typing import Any, Iterable

from .decorators import reactive


def add_reactive_forwarders_0arg(cl: Any, functions: Iterable[str]):
    """
    For operators and methods that don't modify a state of an object (__neg_, etc.).
    """

    def add_one(cl: Any, name):
        def func(self):
            @reactive
            def reactive_f(self_unwrapped):
                return getattr(self_unwrapped, name)()

            return reactive_f(self._target())

        setattr(cl, name, func)

    for name in functions:
        add_one(cl, name)


def add_reactive_forwarders_1arg(cl: Any, functions: Iterable[str]):
    """
    For operators and methods that don't modify a state of an object (__add_, __getitem__, etc.).
    """

    def add_one(cl: Any, name):
        def func(self, arg1):
            @reactive
            def reactive_f(self_unwrapped, other):
                return getattr(self_unwrapped, name)(other)

            return reactive_f(self._target(), arg1)

        setattr(cl, name, func)

    for name in functions:
        add_one(cl, name)


def add_assignop_forwarders(cl: Any, functions: Iterable[str]):
    """
    For operators like '+=' and one-arg functions like append, remove
    """

    def add_one(cl: Any, total_op_name, op):
        def func(self, arg1):
            target = self._target()
            self_unwrapped = target.__inner__
            target.__inner__ = op(self_unwrapped, arg1)
            target.__notifier__.notify_observers()

        setattr(cl, total_op_name, func)

    for op_name in functions:
        assert op_name.startswith('__')
        assert op_name.endswith('__')
        add_one(cl, op_name, getattr(operator, op_name[2:-2]))


def add_modifying_forwarders_1arg(cl: Any, functions: Iterable[str]):
    """
    For operators like '+=' and one-arg functions like append, remove
    """

    def add_one(cl: Any, name):
        def func(self, arg1):
            target = self._target()
            self_unwrapped = target.__inner__
            res = getattr(self_unwrapped, name)(arg1)
            target.__notifier__.notify_observers()
            return res

        setattr(cl, name, func)

    for name in functions:
        add_one(cl, name)


def add_modifying_forwarders_2arg(cl: Any, functions: Iterable[str]):
    """
    __setitem__, anything else?
    """

    def add_one(cl: Any, name):
        def func(self, arg1, arg2):
            target = self._target()
            self_unwrapped = target.__inner__
            res = getattr(self_unwrapped, name)(arg1, arg2)
            target.__notifier__.notify_observers()
            return res

        setattr(cl, name, func)

    for name in functions:
        add_one(cl, name)


UNARY_OPERATORS = [
    '__neg__',
    '__pos__',
    '__abs__',
    '__invert__',

    '__round__',
    '__trunc__',
    '__floor__',
    '__ceil__',
]

BINARY_OPERATORS = [
    # arith
    '__add__',
    '__sub__',
    '__mul__',
    # '__div__',
    '__floordiv__',
    '__truediv__',
    '__mod__',
    '__divmod__',
    '__pow__',
    '__radd__',
    '__rsub__',
    '__rmul__',
    # '__rdiv__',
    '__rfloordiv__',
    '__rtruediv__',
    '__rmod__',
    '__rdivmod__',
    '__rpow__',
    # logic
    '__and__',
    '__or__',
    '__xor__',
    '__lshift__',
    '__rshift__',
    '__rand__',
    '__ror__',
    '__rxor__',
    '__rlshift__',
    '__rrshift__',
]

CMP_OPERATORS = [
    '__eq__',
    '__ge__',
    '__gt__',
    '__le__',
    '__lt__',
    '__ne__',
]

OTHER_NONMODYFING_0ARG = [
    '__len__',
    '__length_hint__',
    '__reversed__',
    '__iter__',
]

OTHER_NONMODYFING_1ARG = [
    '__getitem__',
    '__missing__',
    '__contains__',
]

# TODO more


ASSIGN_MOD_OPERATORS = [
    # arith
    '__iadd__',
    '__isub__',
    '__imul__',
    # '__idiv__',
    '__ifloordiv__',
    '__itruediv__',
    '__imod__',
    '__ipow__',

    # logic
    '__iand__',
    '__ior__',
    '__ixor__',

    '__ilshift__',
    '__irshift__',
]

OTHER_MODYFING_1ARG = [
    '__delitem__',
    '',
]

OTHER_MODYFING_2ARG = [
    '__setitem__',
    '',
]


class ForwarderBase:
    @abstractmethod
    def _target(self):
        """
        Forwarded methods are called on the object returned by this function.
        :return:
        """


class CommonForwarders(ForwarderBase):
    def __bool__(self):
        return bool(self._target().__inner__)

    def __str__(self):
        return self._target().__inner__.__str__()

    def __bytes__(self):
        return self._target().__inner__.__bytes__()

    def __format__(self, format_spec):
        return format(self._target().__inner__, format_spec)


add_reactive_forwarders_0arg(CommonForwarders, UNARY_OPERATORS + OTHER_NONMODYFING_0ARG)
add_reactive_forwarders_1arg(CommonForwarders, BINARY_OPERATORS + CMP_OPERATORS + OTHER_NONMODYFING_1ARG)

add_assignop_forwarders(CommonForwarders, ASSIGN_MOD_OPERATORS)
add_modifying_forwarders_1arg(CommonForwarders, OTHER_MODYFING_1ARG)

add_modifying_forwarders_2arg(CommonForwarders, OTHER_MODYFING_2ARG)


class Forwarder2:

    @reactive
    def __getattr__(self_raw, item):
        return getattr(self_raw, item)

    # @reactive
    # def __setattr__(self_raw, key, value):
    #    return setattr(self_raw, key, value)

    def __delattr__(self, key):
        delattr(self.__inner__.target(), key)
        self.__notifier__.notify_observers()

    @reactive
    def __call__(self_raw, *args, **kwargs):
        return self_raw(*args, **kwargs)

    @reactive
    def __len__(self_raw):
        return len(self_raw)

    @reactive
    def __contains__(self_raw, item):
        return item in self_raw

    @reactive
    def __getitem__(self_raw, item):
        return self_raw[item]

    def __setitem__(self, key, value):
        self[key] = value

    def __delitem__(self, key, value):
        del self.raw[key]

    @reactive
    def __missing__(self_raw, key):
        return self_raw.__missing__(key)

    def __imatmul__(self, value):
        self.__inner__.set_raw(value)

    def __bool__(self):
        return self.raw.__bool__()

        # TODO: rest of arithmetic and logic functions (http://www.diveintopython3.net/special-method-names.html)

    # __complex__
    # __int__
    # __float__
    # __str__
    # __hex__
    # __oct__
    # __unicode__

    # __len__
    # __reversed__
    # __iter__
    # __index__

    # __repr__
    # __call__

    # __long__
    # __init__
    # __instancecheck__
    # __rcmp__
    # __class__
    # __cmp__
    # __coerce__
    # __contains__
    # __del__
    # __delattr__
    # __delete__
    # __delitem__
    # __delslice__
    # __dict__
    # __get__
    # __getattr__
    # __getattribute__
    # __getitem__
    # __getslice__
    # __hash__
    # __metaclass__
    # __mro__
    # __new__
    # __nonzero__
    # __pos__
    # __set__
    # __setattr__
    # __setitem__
    # __setslice__
    # __slots__
    # __subclasscheck__
    # __weakref__
