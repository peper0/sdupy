import asyncio

import numpy as np
from reactive import reactive


def reactive_task(**kwargs):
    pass


def test():
    print("dfyy")


class PlotBind:
    def __init__(self):
        self.plot = None
        pass

    @reactive
    def update(self, plot_brick, data):
        if self.plot:
            self.plot.remove()

        print("updating plot with data %s" % data)
        self.plot, = plot_brick.axes.plot(data)
        plot_brick.draw()


def gen_random(n):
    for i in range(n):
        yield np.random.uniform(0, 1)


@reactive
def add(a, b):
    return a + b


@reactive
async def gen(n, t=1):
    for i in range(n):
        await asyncio.sleep(t)
        yield 1 + i * i


@reactive
async def clocked(interval, gen):
    for i in gen:
        await asyncio.sleep(interval)
        yield i


@reactive
async def append(gen):
    res = []
    async for i in gen:
        res.append(i)
        yield res


@reactive
async def prepend(gen):
    res = []
    async for i in gen:
        res.insert(0, i)
        yield res


@reactive
async def tail(array, count):
    a = np.array(array)

    res = []
    async for i in gen:
        res.insert(0, i)
        yield res


@reactive_with_state(task=None)
def generated_var(self, gen):
    async def feed():
        async for i in gen:
            self.set(i)

    if self.task:
        self.task.cancel()
    self.task = asyncio.ensure_future(feed())  # type: asyncio.Task
    self.task.add_done_callback(rethrow)


@reactive(state=dict(plot=None))
async def plot(state, plot_brick, data):
    if state['plot']:
        state['plot'].remove()

    print("updating plot with data %s" % data)
    if data:
        state['plot'], = plot_brick.axes.plot(data)
        plot_brick.draw()


@reactive_task(args_as_generator=('data',), args_as_vars=('plot_brick'))
async def plot(generator, plot_brick):
    plot_line = None
    async for (data,) in generator:
        if plot_line:
            plot_line.remove()

        print("updating plot with data %s" % data)
        if data:
            plot_line, = plot_brick.axes.plot(data)
            plot_brick.draw()

    if plot_line:
        plot_line.remove()


@reactive_gen()
async def plot(data, plot_brick):
    plot_line, = plot_brick.axes.plot(data)
    plot_brick.draw()
    yield
    plot_line.remove()


def plot2(self, plot_brick, data):
    state = object()
    state.plot = None

    @reactive()
    async def update_plot(plot_brick, data):

        if state.plot:
            state.plot.remove()

        print("updating plot with data %s" % data)
        if data:
            state.plot, = plot_brick.axes.plot(data)
            plot_brick.draw()

    return update_plot(plot_brick, data)


async def plot3(plot_brick, data_gen):
    line = None

    async for data in data_gen:
        if line:
            line.remove()

        print("updating plot with data %s" % data)
        if data:
            line, = plot_brick.axes.plot(data)
            plot_brick.draw()


@reactive_task()
async def rec_telem(output, address):
    async for packet in receive(address):
        output.set(parse_tele(packet))


@reactive_task(outputs=('t1', 't2'))
async def rec_telem(output, address):
    async for packet in receive(address):
        pt = parse_tele(packet)
        if pt.index == 1:
            output.t1.set(pt)
        elif pt.index == 2:
            output.t2.set(pt)

# @reactive(by_var=('val_gen',), generated_output=True)
# def plot3(data_gen, style):
#     plot_line=None
#     for i in val_gen:
#         result += pow(i, exponent)
#         yield result
#
# @reactive(by_var=('val_gen',), generated_output=True)
# def cumulate2(val_gen, exponent):
#     result = 0
#     for i in val_gen:
#         result += pow(i, exponent)
#         yield result
