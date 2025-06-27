from sdupy.pyreactive.refresher import wait_for_var
from .common import is_wrapper, unwrap, unwrap_exception, unwrapped, notify
from .decorators import reactive, reactive_finalizable
from .var import Constant, Var, Wrapped, const, var, volatile

__ALL__ = [
    'reactive',
    'reactive_finalizable',
    'wait_for_var',
    'is_wrapper',
    'unwrap',
    'unwrap_exception',
    'unwrapped',
    'notify',
    'Constant',
    'Var',
    'Wrapped',
    'const',
    'var',
    'volatile',
]


@reactive
def make_list(*args):
    return [a for a in args]


@reactive
def make_tuple(*args):
    return tuple(args)


make_dict = reactive(dict)


def rewrap_dict(d: dict):
    @reactive
    def foo(keys, *values):
        return {k: v for k, v in zip(keys, values)}

    return foo(d.keys(), *d.values())
