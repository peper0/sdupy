from typing import Iterable

from sdupy.pyreactive.decorators import reactive
from sdupy.pyreactive.var import NotInitializedError, volatile


def bind_vars(*settable_vars, readonly_vars=tuple()):
    def set_if_inequal(var_to_set, new_value):
        try:
            is_equal = (var_to_set.__inner__ == new_value)
            if isinstance(is_equal, Iterable):
                # e.g. numpy array comparison
                is_equal = all(is_equal)
            if is_equal:
                return
        except NotInitializedError:
            pass
        var_to_set.__inner__ = new_value

    @reactive
    def set_all(value):
        for var in settable_vars:
            set_if_inequal(var, value)

    return [volatile(set_all(var)) for var in tuple(settable_vars) + tuple(readonly_vars)]


def none_if_error(v):
    @reactive(pass_args=['v'], dep_only_args=['v2'])
    def helper(v):
        try:
            return v.__inner__
        except Exception:
            return None

    return helper(v, v2=v)


@reactive
def error_if_none(v, msg="Value is None"):
    if v is None:
        raise ValueError(msg)
    return v

def pickn(iterable, n):
    return (v for v, _ in zip(iterable, range(n)))
