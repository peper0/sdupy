from sdupy.reactive.refresher import wait_for_var
from .common import is_wrapper, unwrap, unwrap_exception, unwrapped
from .decorators import reactive, reactive_finalizable
from .var import Constant, Var, Wrapped, const, var


@reactive
def make_list(*args):
    return [a for a in args]


@reactive
def make_tuple(*args):
    return tuple(args)


make_dict = reactive(dict)
