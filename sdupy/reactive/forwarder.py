import operator
from abc import abstractmethod
from functools import wraps
from math import ceil, floor, trunc

from sdupy.reactive.wrapping import add_assignop_forwarders, add_notifying_forwarders, add_reactive_forwarders
from .decorators import reactive

UNARY_OPERATORS = [
    ('__neg__', operator.__neg__),
    ('__pos__', operator.__pos__),
    ('__abs__', operator.__abs__),
    ('__invert__', operator.__invert__),
    ('__round__', round),
    ('__trunc__', trunc),
    ('__floor__', floor),
    ('__ceil__', ceil),
]


def right_2arg(func):
    @wraps(func)
    def f(a1, a2):
        return func(a2, a1)

    return f


BINARY_OPERATORS = [
    # arith         # arith        
    ('__add__', operator.__add__),
    ('__sub__', operator.__sub__),
    ('__mul__', operator.__mul__),
    ('__floordiv__', operator.__floordiv__),
    ('__truediv__', operator.__truediv__),
    ('__mod__', operator.__mod__),
    ('__divmod__', divmod),
    ('__pow__', operator.__pow__),
    ('__radd__', right_2arg(operator.__add__)),
    ('__rsub__', right_2arg(operator.__sub__)),
    ('__rmul__', right_2arg(operator.__mul__)),
    ('__rfloordiv__', right_2arg(operator.__floordiv__)),
    ('__rtruediv__', right_2arg(operator.__truediv__)),
    ('__rmod__', right_2arg(operator.__mod__)),
    ('__rdivmod__', right_2arg(divmod)),
    ('__rpow__', right_2arg(operator.__pow__)),
    # logic
    ('__and__', operator.__and__),
    ('__or__', operator.__or__),
    ('__xor__', operator.__xor__),
    ('__lshift__', operator.__lshift__),
    ('__rshift__', operator.__rshift__),
    ('__rand__', operator.__and__),
    ('__ror__', right_2arg(operator.__or__)),
    ('__rxor__', right_2arg(operator.__xor__)),
    ('__rlshift__', right_2arg(operator.__lshift__)),
    ('__rrshift__', right_2arg(operator.__rshift__)),
]

CMP_OPERATORS = [
    ('__eq__', operator.__eq__),
    ('__ge__', operator.__ge__),
    ('__gt__', operator.__gt__),
    ('__le__', operator.__le__),
    ('__lt__', operator.__lt__),
    ('__ne__', operator.__ne__),
]

OTHER_NONMODYFING_0ARG = [
    ('__len__', len),
    ('__length_hint__', operator.length_hint),
    ('__reversed__', reversed),
    # '__iter__',  # it's not so simple
]

OTHER_NONMODYFING_1ARG = [
    ('__getitem__', operator.getitem),
    # ('__missing__',
    ('__contains__', operator.contains),
]

ASSIGN_MOD_OPERATORS = [
    # arith
    ('__iadd__', operator.__iadd__),
    ('__isub__', operator.__isub__),
    ('__imul__', operator.__imul__),

    ('__ifloordiv__', operator.__ifloordiv__),
    ('__itruediv__', operator.__itruediv__),
    ('__imod__', operator.__imod__),
    ('__ipow__', operator.__ipow__),
    # logic        operator.# logic
    ('__iand__', operator.__iand__),
    ('__ior__', operator.__ior__),
    ('__ixor__', operator.__ixor__),
    ('__ilshift__', operator.__ilshift__),
    ('__irshift__', operator.__irshift__),
]

OTHER_MODYFING_1ARG = [
    ('__delitem__', operator.delitem),
]

OTHER_MODYFING_2ARG = [
    ('__setitem__', operator.setitem),
]


class ForwarderBase:
    @abstractmethod
    def _target(self):
        """
        Forwarded methods are called on the object returned by this function.
        :return:
        """


class ConstForwarders(ForwarderBase):
    def __bool__(self):
        return bool(self._target().__inner__)

    def __str__(self):
        return self._target().__inner__.__str__()

    def __bytes__(self):
        return self._target().__inner__.__bytes__()

    def __format__(self, format_spec):
        return format(self._target().__inner__, format_spec)


class MutatingForwarders(ForwarderBase):
    pass


add_reactive_forwarders(ConstForwarders, UNARY_OPERATORS + OTHER_NONMODYFING_0ARG)
add_reactive_forwarders(ConstForwarders, BINARY_OPERATORS + CMP_OPERATORS + OTHER_NONMODYFING_1ARG)

add_assignop_forwarders(ConstForwarders, ASSIGN_MOD_OPERATORS)
add_notifying_forwarders(MutatingForwarders, OTHER_MODYFING_1ARG + OTHER_MODYFING_2ARG)


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
    # __delslice__
    # __dict__
    # __get__
    # __getattr__
    # __getattribute__
    # __getslice__
    # __hash__
    # __metaclass__
    # __mro__
    # __new__
    # __nonzero__
    # __pos__
    # __set__
    # __setattr__
    # __setslice__
    # __slots__
    # __subclasscheck__
    # __weakref__
