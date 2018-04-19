import asyncio
from abc import abstractmethod
from typing import Callable, Coroutine, Union, Generic, TypeVar


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


T = TypeVar('T')

class Wrapped(Generic[T]):
    @property
    @abstractmethod
    def __notifier__(self):
        """
        A notifier, that will notify whenever a reactive function that used this object should be called again.
        """
        pass

    @property
    @abstractmethod
    def __inner__(self) -> T:
        """
        Return the object that is wrapped.
        It's usually a raw non observable object, however inside "Proxy" it's used to hold a reference to any object (possibly other Proxy or other wrapper)
        It will be taken by the @reactive function and passed to the body of the function.
        """
        pass


def is_wrapper(v):
    return isinstance(v, Wrapped)


def unwrap(v: Wrapped[T]) -> T:
    return v.__inner__


def unwrap_exception(v):
    try:
        v.__inner__
        return None
    except Exception as e:
        return e


def unwrap_def(v, val_on_exception = None):
    try:
        return v.__inner__
    except Exception as e:
        return val_on_exception


def unwrapped(v: Union[T, Wrapped[T]]) -> T:
    if is_wrapper(v):
        return unwrap(v)
    else:
        return v
