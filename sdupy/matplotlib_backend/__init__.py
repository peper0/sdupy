"""
One day we'll make full-featured reactive matplotlib backend. But for now, only prevent using some other that could do
a mess. Nevertheless, we should not use pyplot interface directly (use sdupy.axes())
"""

from matplotlib.backend_bases import FigureCanvasBase, FigureManagerBase, _Backend


class FigureCanvasSdupy(FigureCanvasBase):
    def __init__(self, figure):
        raise NotImplementedError()


class FigureManagerSdupy(FigureManagerBase):
    def __init__(self, canvas, num):
        super().__init__(self, canvas, num)
        raise NotImplementedError()


@_Backend.export
class _BackendSdupy(_Backend):
    FigureCanvas = FigureCanvasSdupy
    FigureManager = FigureManagerSdupy

    @staticmethod
    def mainloop():
        # allow KeyboardInterrupt exceptions to close the plot window.
        raise NotImplementedError()
