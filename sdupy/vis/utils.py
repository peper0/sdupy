from sdupy import vis


def link_pg_axes(first: str, second: str, which={'x', 'y'}):
    w1 = vis.widget(first).view
    w2 = vis.widget(second).view
    if 'x' in which:
        w1.setXLink(w2)
    if 'y' in which:
        w1.setYLink(w2)


def pg_roi_add_8handles(roi_item):
    for x in [0, 0.5, 1]:
        for y in [0, 0.5, 1]:
            if not (x == 0.5 and y == 0.5):
                roi_item.addScaleHandle([x, y], [1 - x, 1 - y])