from typing import Iterable

from sdupy.reactive import reactive
from sdupy.reactive.var import Observable


def get_subobservable(self: Observable, name: str) -> Observable:
    if not hasattr(self.OBS, '_subobservables'):
        setattr(self.OBS, '_subobservables', dict())
    return self.OBS._subobservables.setdefault(name, Observable())


def observable_method(unbound_method, observed: Iterable[str], notified: Iterable[str]):
    # @reactive(other_deps=[get_subobservable observed)
    @reactive(args_as_vars=[0], dep_only_args=['additional_deps0', 'additional_deps1', 'additional_deps2'])  # FIXME ;)
    def wrapped(self, *args, **kwargs):
        res = unbound_method(self.get(), *args, **kwargs)
        for observable in notified:
            get_subobservable(self, observable).notify_observers()
        return res

    def wrapped2(self, *args, **kwargs):
        add_deps = {"additional_deps{}".format(i): get_subobservable(self, obs) for i, obs in enumerate(observed)}

        return wrapped(self, *args, **kwargs, **add_deps)

    return wrapped2


def getter(unbound_method, observed):
    return observable_method(unbound_method, observed=observed, notified=[])


def setter(unbound_method, notified):
    return observable_method(unbound_method, observed=[], notified=notified)
