import asyncio
from abc import abstractmethod
from typing import Callable, Coroutine, Union


def ensure_coro_func(f):
    if asyncio.iscoroutinefunction(f):
        return f
    elif hasattr(f, '__call__'):
        async def async_f(*args, **kwargs):
            return f(*args, **kwargs)

        return async_f


CoroutineFunction = Callable[..., Coroutine]

MaybeAsyncFunction = Union[Callable, CoroutineFunction]
NotifyFunc = Union[Callable[[], None], Callable[[], Coroutine]]


class WrapperInterface:
    @property
    @abstractmethod
    def __notifier__(self) -> 'Notifier':
        """
        A notifier, that will notify whenever a reactive function that used this object should be called again.
        """
        pass

    @property
    @abstractmethod
    def __inner__(self):
        """
        Return the object that is wrapped.
        It's usually a raw non observable object, however inside "Proxy" it's used to hold a reference to any object (possibly other Proxy or other wrapper)
        It will be taken by the @reactive function and passed to the body of the function.
        """
        pass


def is_wrapper(v):
    return isinstance(v, WrapperInterface)


def unwrap(v):
    return v.__inner__


def unwrap_exception(v):
    try:
        v.__inner__
        return None
    except Exception as e:
        return e


def unwrapped(v):
    if is_wrapper(v):
        return unwrap(v)
    else:
        return v
