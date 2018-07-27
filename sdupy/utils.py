import logging
from functools import wraps


#FIXME: rename to "log_errors" or "errors_to_log"
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


logger = logging.getLogger('trace')


def trace(f=None):
    def wrap(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                res = f(*args, **kwargs)
                logger.info("{}({} {}) -> {}".format(f.__name__, args, kwargs, res))
                return res
            except Exception as e:
                logger.info("{}({} {}) # {}".format(f.__name__, args, kwargs, e))
                raise
        return wrapper

    if f:  # a shortcut
        return wrap(f)
    else:
        return wrap


