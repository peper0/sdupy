import asyncio
import sip

# import public
from main_window import MainWindow

sip.setapi("QString", 2)
sip.setapi("QVariant", 2)

import sys

from quamash import QEventLoop, QApplication

app = QApplication(sys.argv)

loop = QEventLoop(app)
asyncio.set_event_loop(loop)  # NEW must set the event loop

window = MainWindow()
window.show()


# con = widgets.make_console(window)
# window.addDockWidget(Qt.RightDockWidgetArea, con)


async def async_main():
    # window.add_plot()
    for i in range(100):
        await asyncio.sleep(1)
        # con.setWindowTitle("con %d" % i)

        # pb = public.PlotBind()
        # pb.update(window.plot, [1, 2, 3])


main_task = asyncio.ensure_future(async_main())

try:
    with loop:  ## context manager calls .close() when loop completes, and releases all resources
        loop.run_forever()
        #    loop.run_until_complete(async_main())
finally:
    pass
    # main_task.cancel()
