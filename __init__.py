import sip

sip.setapi("QString", 2)
sip.setapi("QVariant", 2)

import asyncio
from ipykernel.eventloops import register_integration

# import public
from .main_window import MainWindow

import sys

import quamash

current_main_window = None  # type: MainWindow
state_name = 'default'


@register_integration('sdupy')
def run_loop_in_jupyter(kernel):
    sys.stderr.write("starting 'sdupy' mainloop\n")
    print('starting "sdupy" mainloop')
    init_quamash()
    loop = asyncio.get_event_loop()  # type: quamash.QEventLoop

    def kernel_handler():
        # print("kernel")
        loop.call_soon(kernel.do_one_iteration)
        loop.call_later(kernel._poll_interval, kernel_handler)

    loop.call_soon(kernel_handler)
    with loop:  ## context manager calls .close() when loop completes, and releases all resources
        loop.run_forever()
    print("sdupy mainloop finished")


def run_loop():
    init_quamash()
    loop = asyncio.get_event_loop()
    with loop:  ## context manager calls .close() when loop completes, and releases all resources
        loop.run_forever()


def init_quamash():
    app = quamash.QApplication(sys.argv)
    loop = quamash.QEventLoop(app)
    asyncio.set_event_loop(loop)  # NEW must set the event loop


def gcmw() -> MainWindow:
    """
    Get current main window.
    """
    if not current_main_window:
        main_window(state_name)
    return current_main_window


def main_window(state_name_):
    global state_name
    global current_main_window
    state_name = state_name_
    main_window = MainWindow(state_name=state_name)
    current_main_window = main_window
    main_window.show()

    def window_closed():
        global current_main_window
        if current_main_window == main_window:
            current_main_window = None

    main_window.close_callback = window_closed()

    return main_window
