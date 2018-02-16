import asyncio

from ipykernel.eventloops import register_integration

from studioapp import init_loop


@register_integration('studio')
def loop_asyncio(kernel):
    init_loop()

    loop = asyncio.get_event_loop()

    def kernel_handler():
        # print("kernel")
        loop.call_soon(kernel.do_one_iteration)
        loop.call_later(kernel._poll_interval, kernel_handler)

    loop.call_soon(kernel_handler)
    try:
        with loop:  ## context manager calls .close() when loop completes, and releases all resources
            loop.run_forever()
    finally:
        pass
