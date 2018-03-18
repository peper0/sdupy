from abc import abstractmethod
from typing import Any, Iterable

from .decorators import reactive


def add_reactive_forwarders_1arg(cl: Any, functions: Iterable[str]):
    def add_one(cl: Any, name):
        def func(self, arg1):
            @reactive
            def reactive_f(self_unwrapped, other):
                return getattr(self_unwrapped, name)(other)

            return reactive_f(self._target(), arg1)

        setattr(cl, name, func)

    for name in functions:
        add_one(cl, name)


ARITH_BINARY_OPERATORS = [
    '__add__',
    '__sub__',
    '__mul__',
    '__div__',
    '__floordiv__',
    '__truediv__',
    '__mod__',
    '__divmod__',
    '__pow__',
    '__radd__',
    '__rsub__',
    '__rmul__',
    '__rdiv__',
    '__rfloordiv__',
    '__rtruediv__',
    '__rmod__',
    '__rdivmod__',
    '__rpow__',
]

LOGIC_BINARY_OPERATORS = [
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

# TODO more

NONMODYFING_OPERATORS = ARITH_BINARY_OPERATORS + LOGIC_BINARY_OPERATORS + CMP_OPERATORS


class ForwarderBase:
    @abstractmethod
    def _target(self):
        """
        Forwarded methods are called on the object returned by this function.
        :return:
        """


class CommonForwarders(ForwarderBase):
    def __bool__(self):
        return self._target().__inner__.__bool__()

    def __bytes__(self):
        return bytes(self._target().__inner__)

    def __format__(self, format_spec):
        return format(self._target().__inner__, format_spec)


add_reactive_forwarders_1arg(CommonForwarders, NONMODYFING_OPERATORS)


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

    # __iadd__
    # __isub__
    # __imul__
    # __idiv__
    # __ifloordiv__
    # __itruediv__
    # __imod__
    # __ipow__

    # __iand__
    # __ior__
    # __ixor__

    # __ilshift__
    # __irshift__

    # __complex__
    # __int__
    # __float__
    # __str__
    # __hex__
    # __oct__
    # __unicode__

    # __invert__
    # __neg__
    # __abs__

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
