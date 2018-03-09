import asyncio

from pydev_ipython.inputhook import set_inputhook

from sdupy.mainloop.common import init_quamash
from .common import test_asyncio


def asyncio_inputhook():
    loop = asyncio.get_event_loop()
    timer = asyncio.sleep(0.01)
    loop.run_until_complete(timer)


def install():
    print("registering ipython gui mainloop...")
    init_quamash()
    set_inputhook(asyncio_inputhook)
    test_asyncio()
