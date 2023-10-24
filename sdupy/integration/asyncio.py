import asyncio

from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication

if QApplication.instance() is None:
    app = QApplication(['sdupy'])


async def run_qt_for_a_while():
    app.processEvents(QtCore.QEventLoop.AllEvents, 50)
    asyncio.create_task(run_qt_for_a_while())


def install():
    asyncio.create_task(run_qt_for_a_while())


def run_mainloop():
    print("Ignoring 'run_mainloop' - mainloop is integrated with current shell")
