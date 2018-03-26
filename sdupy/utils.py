import logging
from functools import wraps


def ignore_errors(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception:
            logging.exception("ignoring error")

    return wrapper
