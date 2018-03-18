from sdupy.reactive.refresher import wait_for_var
from .decorators import reactive, reactive_finalizable
from .var import Var


@reactive
def getitem(obj, item):
    return obj[item]


@reactive
def getitem_default(obj, item, def_val=None):
    try:
        return obj[item]
    except Exception:
        return def_val


def unpack(var_with_tuple):
    return tuple(getitem(var_with_tuple, i) for i in range(len(var_with_tuple.get())))
