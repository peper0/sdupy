import asyncio
import sip

# import public
from .main_window import MainWindow

sip.setapi("QString", 2)
sip.setapi("QVariant", 2)

import sys

from quamash import QEventLoop, QApplication

default_main_window = None  # type: MainWindow


def gcmw() -> MainWindow:
    """
    Get current main window.
    """
    return default_main_window


def init_loop():
    app = QApplication(sys.argv)

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)  # NEW must set the event loop


def run_loop():
    loop = asyncio.get_event_loop()
    try:
        with loop:  ## context manager calls .close() when loop completes, and releases all resources
            loop.run_forever()
            #    loop.run_until_complete(async_main())
    finally:
        pass
        # main_task.cancel()


def start(state_name):
    global default_main_window
    window = MainWindow(state_name=state_name)
    default_main_window = window
    window.show()
    return window
