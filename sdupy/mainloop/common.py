import asyncio
import sys

import quamash

app = None
loop = None


def init_quamash():
    global app
    global loop
    if app is None or loop is None:
        app = quamash.QApplication(sys.argv)
        loop = quamash.QEventLoop(app)
        asyncio.set_event_loop(loop)  # NEW must set the event loop


asyncio_is_working = False


async def asyncio_test_coro():
    global asyncio_is_working
    asyncio_is_working = True
    asyncio.sleep(1)
    sys.stderr.write("asyncio loop is working!\n")


def test_asyncio():
    asyncio.ensure_future(asyncio_test_coro())
