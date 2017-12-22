factories = dict()


def register_widget(name):
    def register_class(f):
        factories[name] = f
        return f

    return register_class


def register_factory(name):
    def register_factory_function(f):
        factories[name] = f
        return f

    return register_factory_function
