import matplotlib.pyplot as plt
import numpy as np
from IPython.lib import guisupport
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget

from .common.register import register_factory


class QIPythonWidget(RichJupyterWidget):
    """ Convenience class for a live IPython console widget. We can replace the standard banner using the customBanner argument"""

    def __init__(self, customBanner=None, *args, **kwargs):
        if customBanner != None: self.banner = customBanner
        super(QIPythonWidget, self).__init__(*args, **kwargs)
        self.kernel_manager = kernel_manager = QtInProcessKernelManager()
        kernel_manager.start_kernel()
        kernel_manager.kernel.gui = 'qt'
        self.kernel_client = kernel_client = self._kernel_manager.client()
        kernel_client.start_channels()

        def stop():
            kernel_client.stop_channels()
            kernel_manager.shutdown_kernel()
            guisupport.get_app_qt4().exit()

        self.exit_requested.connect(stop)

    def pushVariables(self, variableDict):
        """ Given a dictionary containing name / value pairs, push those variables to the IPython console widget """
        self.kernel_manager.kernel.shell.push(variableDict)

    def clearTerminal(self):
        """ Clears the terminal """
        self._control.clear()

    def printText(self, text):
        """ Prints some plain text to the console """
        self._append_plain_text(text)

    def executeCommand(self, command):
        """ Execute a command in the frame of the console widget """
        self._execute(command, False)


def print_process_id():
    import os
    print('Process ID is:', os.getpid())


@register_factory("my_console")
def make_console(parent=None):
    ipyConsole = QIPythonWidget(customBanner="ble\n")
    ipyConsole.pushVariables(
        {"foo": "ddd", "print_process_id": print_process_id, "window": parent, "plt": plt, 'np': np})
    ipyConsole.printText(
        "The variable 'foo' and the method 'print_process_id()' are available. Use the 'whos' command for information.")
    ipyConsole.executeCommand("%load_ext autoreload\n")
    ipyConsole.executeCommand("%autoreload 2\n")
    # ipyConsole.executeCommand("import public as p\n")
    # ipyConsole.executeCommand("import asyncio\n")
    # ipyConsole.executeCommand("from reactive import Var, reactive\n")
    return ipyConsole
