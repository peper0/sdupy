from matplotlib import pyplot as plt

from .. import reactive_finalizable
from ..var import Wrapper
from ..wrapping import getter, reactive_setter


def default_remove_plot(plot_res, axes: plt.Axes):
    if isinstance(plot_res, list) or isinstance(plot_res, tuple):
        for i in plot_res:
            default_remove_plot(i, axes)
    else:
        plot_res.remove()

        pass


def plot_method(unbound_method, remove_func=default_remove_plot):
    @reactive_finalizable()
    def wrapped(self, *args, **kwargs):
        res = unbound_method(self, *args, **kwargs)
        figure = self.get_figure()
        assert figure is not None
        canvas = figure.canvas
        canvas.draw_idle()
        yield res

        if res and remove_func:
            remove_func(res, self.axes)
            canvas.draw_idle()

    def wrapped2(self, *args, **kwargs):
        return wrapped(self, *args, **kwargs)

    return wrapped2


class ReactiveAxes(Wrapper):
    def __init__(self, axes: plt.Axes):
        assert isinstance(axes, plt.Axes)
        super().__init__(axes)

    # Plotting.Basic
    plot = plot_method(plt.Axes.plot)
    errorbar = plot_method(plt.Axes.errorbar)
    scatter = plot_method(plt.Axes.scatter)
    plot_date = plot_method(plt.Axes.plot_date)
    step = plot_method(plt.Axes.step)
    loglog = plot_method(plt.Axes.loglog)
    semilogx = plot_method(plt.Axes.semilogx)
    semilogy = plot_method(plt.Axes.semilogy)
    fill_between = plot_method(plt.Axes.fill_between)
    fill_betweenx = plot_method(plt.Axes.fill_betweenx)
    bar = plot_method(plt.Axes.bar)
    barh = plot_method(plt.Axes.barh)
    stem = plot_method(plt.Axes.stem)
    eventplot = plot_method(plt.Axes.eventplot)
    pie = plot_method(plt.Axes.pie)
    stackplot = plot_method(plt.Axes.stackplot)
    broken_barh = plot_method(plt.Axes.broken_barh)
    vlines = plot_method(plt.Axes.vlines)
    hlines = plot_method(plt.Axes.hlines)
    hlines = plot_method(plt.Axes.hlines)
    fill = plot_method(plt.Axes.fill)

    # Plotting.Spans
    axhline = plot_method(plt.Axes.axhline)
    axhspan = plot_method(plt.Axes.axhspan)
    axvline = plot_method(plt.Axes.axvline)
    axvspan = plot_method(plt.Axes.axvspan)

    # Plotting.Array
    imshow = plot_method(plt.Axes.imshow)
    matshow = plot_method(plt.Axes.matshow)
    pcolor = plot_method(plt.Axes.pcolor)
    pcolorfast = plot_method(plt.Axes.pcolorfast)
    pcolormesh = plot_method(plt.Axes.pcolormesh)
    spy = plot_method(plt.Axes.spy)

    # TODO: rest from https://matplotlib.org/api/axes_api.html#plotting

    get_xlim = getter(plt.Axes.get_xlim, ['xlim'])
    set_xlim = reactive_setter(plt.Axes.set_xlim, ['xlim'])
    get_ylim = getter(plt.Axes.get_xlim, ['xlim'])
    set_ylim = reactive_setter(plt.Axes.set_xlim, ['xlim'])

    # TODO: rest from https://matplotlib.org/api/axes_api.html#plotting
