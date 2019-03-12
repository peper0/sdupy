import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import wraps


#FIXME: rename to "log_errors" or "errors_to_log"
from typing import Callable, T, Awaitable


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


def make_async_using_thread(f: Callable[..., T]) -> Callable[..., Awaitable[T]]:
    @wraps(f)
    async def wrapped(*args, **kwargs):
        def bound_f():
            return f(*args, **kwargs)

        with ThreadPoolExecutor(max_workers=1) as executor:
            return await asyncio.get_event_loop().run_in_executor(executor, bound_f)

    return wrapped


def make_sync(f: Callable[..., Awaitable[T]]) -> Callable[..., T]:
    loop = asyncio.get_event_loop()

    @wraps(f)
    def wrapped(*args, **kwargs):
        res = asyncio.run_coroutine_threadsafe(f(*args, **kwargs), loop).result()
        return res

    return wrapped
