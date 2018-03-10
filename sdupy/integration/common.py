import asyncio
import sys

import quamash
from PyQt5 import QtCore

loop = None


class QEventLoop(quamash.QEventLoop):
    def run_for(self, max_time):
        """Run eventloop forever."""
        self.__is_running = True
        self._before_run_forever()
        try:
            self._logger.debug('Starting Qt event loop')
            rslt = self.__app.processEvents(QtCore.QEventLoop.AllEvents, int(max_time * 1000))
            self._logger.debug('Qt event loop ended with result {}'.format(rslt))
            return rslt
        finally:
            self._after_run_forever()
            self.__is_running = False


def init_quamash():
    global loop
    if loop is None:
        loop = QEventLoop()
        asyncio.set_event_loop(loop)  # NEW must set the event loop


asyncio_is_working = False


async def asyncio_test_coro():
    global asyncio_is_working
    asyncio_is_working = True
    asyncio.sleep(1)
    sys.stderr.write("asyncio loop is working!\n")


def test_asyncio():
    asyncio.ensure_future(asyncio_test_coro())
