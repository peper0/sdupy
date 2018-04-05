import asyncio
import sys

from PyQt5.QtWidgets import QApplication

from .common import init_quamash

if QApplication.instance() is None:
    app = QApplication(sys.argv)


def run_mainloop():
    init_quamash()
    loop = asyncio.get_event_loop()
    with loop:  ## context manager calls .close() when loop completes, and releases all resources
        loop.run_forever()
