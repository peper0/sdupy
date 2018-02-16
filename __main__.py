import asyncio

from studioapp import init_loop, run_loop, start


# con = widgets.make_console(window)
# window.addDockWidget(Qt.RightDockWidgetArea, con)


async def test():
    # window.add_plot()
    for i in range(100):
        await asyncio.sleep(1)
        # con.setWindowTitle("con %d" % i)

        # pb = public.PlotBind()
        # pb.update(window.plot, [1, 2, 3])


main_task = asyncio.ensure_future(test())

init_loop()
start('default')
run_loop()
