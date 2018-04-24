from sdupy import reactive
from sdupy.pyreactive.var import NotInitializedError


def bind_vars(*vars):
    def set_if_inequal(var_to_set, new_value):
        try:
            # print("{} is {}".format(repr(var_to_set), var_to_set.__inner__))
            if var_to_set.__inner__ == new_value:
                return
        except NotInitializedError:
            pass
        # print("setting {} to {}".format(repr(var_to_set), new_value))
        var_to_set.__inner__ = new_value

    @reactive
    def set_all(value):
        for var in vars:
            set_if_inequal(var, value)

    return [set_all(var) for var in vars]