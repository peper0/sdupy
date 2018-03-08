from typing import Callable, Dict, NamedTuple


def _get_factory_name(factory):
    return factory.__name__


class FactoryDesc(NamedTuple):
    factory: Callable
    name: str
    pretty_name: str


registered_factories = dict()  # type: Dict[str, FactoryDesc]


def register_widget(pretty_name):
    def register_class(f):
        name = _get_factory_name(f)
        registered_factories[name] = FactoryDesc(factory=f, name=name, pretty_name=pretty_name)
        return f

    return register_class


def register_factory(pretty_name):
    def register_factory_function(f):
        name = _get_factory_name(f)
        registered_factories[name] = FactoryDesc(factory=f, name=name, pretty_name=pretty_name)
        return f

    return register_factory_function
