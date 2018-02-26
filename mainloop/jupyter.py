import asyncio
import sys

from ipykernel.eventloops import register_integration

from .common import init_quamash, test_asyncio


@register_integration('sdupy')
def run_loop_in_jupyter(kernel):
    """
    Can be used as cell magic (%gui sdupy) or installed with install()
    """
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


def install():
    print("registering jupyter gui mainloop...")
    get_ipython().run_line_magic('gui', 'sdupy')
    init_quamash()  # run_line_magic doesn't call run_loop_in_jupyter immediately and we don't want to loose any schedule to the loop
    test_asyncio()
