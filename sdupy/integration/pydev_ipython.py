import asyncio
from contextlib import suppress

from PyQt5.QtWidgets import QApplication
from _pydev_bundle.pydev_import_hook import import_hook_manager
from pydev_ipython.inputhook import set_inputhook

from sdupy.utils import ignore_errors
from .common import QEventLoop, init_quamash, test_asyncio

# bypass some pydev hacks that breaks everything
with suppress(Exception):
    del import_hook_manager._modules_to_patch['matplotlib']
with suppress(Exception):
    del import_hook_manager._modules_to_patch['pyplot']
with suppress(Exception):
    del import_hook_manager._modules_to_patch['pylab']

import matplotlib

matplotlib.use('module://sdupy.matplotlib_backend')
app = None


@ignore_errors
def asyncio_inputhook():
    loop = asyncio.get_event_loop()
    assert loop is not None
    assert isinstance(loop, QEventLoop), "loop is of type {}".format(loop.__class__.__qualname__)
    # run_until_complete(sleep) is bad since it calls QApplication.exit() after timeout
    loop.run_for(0.05)


def install():
    print("registering ipython gui integration...")
    if QApplication.instance() is None:
        global app
        app = QApplication(['sdupy'])
    init_quamash()
    set_inputhook(asyncio_inputhook)
    # test_asyncio()


def run_mainloop():
    print("Ignoring 'run_mainloop' - mainloop is integrated with current shell")
