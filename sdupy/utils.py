import logging
from functools import wraps


def ignore_errors(f=None, *, retval=None):
    def wrap(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception:
                logging.exception("ignoring error")
                return retval
        return wrapper

    if f:  # a shortcut
        return wrap(f)
    else:
        return wrap

