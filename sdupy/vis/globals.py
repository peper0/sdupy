import gc

from sdupy.pyreactive.var import LazySwitchableProxy

global_refs = {}


def store_global_ref(key, value):
    prev = global_refs.get(key)
    if prev is not None:
        if isinstance(prev, LazySwitchableProxy):
            prev._cleanup()
        gc.collect()  # we still rely on destruction

    global_refs[key] = value