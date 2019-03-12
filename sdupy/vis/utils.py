from typing import Sequence, Union

from sdupy import vis, unwrap, reactive_finalizable
from sdupy.pyreactive.var import volatile


def link_pg_axes(slaves: Union[str, Sequence[str]], master: str, which={'x', 'y'}):
    if isinstance(slaves, str):
        slaves = [slaves]
    master_view = vis.widget(master).view
    for slave in slaves:
        try:
            slave_view = vis.widget(slave).view
            if 'x' in which:
                slave_view.setXLink(master_view)
            if 'y' in which:
                slave_view.setYLink(master_view)
        except Exception as e:
            raise Exception("cannot link '{}' to '{}'".format(slave, master)) from e


def link_mpl_axes(axes: Union[str, Sequence[str]], which={'x', 'y'}):
    if isinstance(axes, str):
        axes = [axes]
    master, *slaves = axes
    master_axes = unwrap(vis.axes(master))
    for slave in slaves:
        try:
            slave_axes = unwrap(vis.axes(slave))
            if 'x' in which:
                master_axes.get_shared_x_axes().join(master_axes, slave_axes)
            if 'y' in which:
                master_axes.get_shared_y_axes().join(master_axes, slave_axes)
        except Exception as e:
            raise Exception("cannot link '{}' to '{}'".format(slave, master)) from e


def pg_roi_add_8handles(roi_item):
    for x in [0, 0.5, 1]:
        for y in [0, 0.5, 1]:
            if not (x == 0.5 and y == 0.5):
                roi_item.addScaleHandle([x, y], [1 - x, 1 - y])


def synced_vlines(axes: Union[str, Sequence[str]], x_var):
    def vline_and_click(axes):
        fig = unwrap(axes).figure

        def onclick(event):
            if event.dblclick:
                x_var.set(int(event.xdata))

        @reactive_finalizable
        def add_onclick():
            cid = fig.canvas.mpl_connect('button_press_event', onclick)
            yield
            fig.canvas.mpl_disconnect(cid)

        vline = volatile(axes.axvline(x_var, color="green"))
        onclick_holder = volatile(add_onclick())
        return vline, onclick_holder

    return [vline_and_click(vis.axes(a)) for a in axes]
