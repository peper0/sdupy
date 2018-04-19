from ..decorators import reactive
from ..forwarder import ConstForwarders, MutatingForwarders
from ..var import Wrapper
from ..wrapping import getter, notifying_method


class Sequence(Wrapper):
    __contains__ = getter('__contains__', [''])
    __add__ = getter('__add__', [''])
    __add__ = getter('__add__', [''])
    __mul__ = getter('__mul__', [''])
    __rmul__ = getter('__rmul__', [''])
    __getitem__ = getter('__getitem__', [''])
    __len__ = getter('__len__', [''])
    index = getter('index', [''])
    count = getter('count', [''])


class MutableSequence(Sequence):
    copy = getter('copy', [''])

    __setitem__ = notifying_method('__setitem__', [''])
    __delitem__ = notifying_method('__delitem__', [''])
    append = notifying_method('append', [''])
    clear = notifying_method('clear', [''])
    extend = notifying_method('extend', [''])
    __iadd__ = notifying_method('__iadd__', [''])
    __imul__ = notifying_method('__imul__', [''])
    insert = notifying_method('insert', [''])
    pop = notifying_method('pop', [''])
    remove = notifying_method('remove', [''])
    reverse = notifying_method('reverse', [''])


class List(Wrapper, MutatingForwarders, ConstForwarders):
    def __init__(self, d: list = None):
        super().__init__(d if d is not None else list())

    sort = notifying_method('sort', [''])


class Dict(Wrapper):
    def __init__(self, **kwargs):
        super().__init__(dict(**kwargs))

    __contains__ = getter('__contains__', [''])
    __getitem__ = getter('__getitem__', [''])
    __len__ = getter('__len__', [''])
    # __iter__ = dict.__iter__  # it would need some new wrapping atom: the result of __iter__ may be used only once, so we cannot cache it
    count = getter('count', [''])
    get = getter('get', [''])
    keys = getter('keys', [''])
    values = getter('values', [''])
    items = getter('items', [''])

    __setitem__ = notifying_method('__setitem__', [''])
    __delitem__ = notifying_method('__delitem__', [''])
    clear = notifying_method('clear', [''])
    pop = notifying_method('pop', [''])
    popitem = notifying_method('popitem', [''])
    setdefault = notifying_method('setdefault', [''])
    update = notifying_method('update', [''])
    remove = notifying_method('remove', [''])

    @staticmethod
    @reactive
    def make(**kwargs):
        return Dict(**kwargs)
