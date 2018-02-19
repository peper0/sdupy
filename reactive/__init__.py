from .reactive import reactive
from .var import VarBase, Var, wait_for_var


@reactive()
def getitem(obj, item):
    return obj[item]


def unpack(var_with_tuple):
    return tuple(getitem(var_with_tuple, i) for i in range(len(var_with_tuple.get())))
