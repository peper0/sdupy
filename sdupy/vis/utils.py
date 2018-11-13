from typing import Sequence, Union

from sdupy import vis, unwrap


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