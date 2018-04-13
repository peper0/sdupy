from math import isfinite
from typing import Any, Mapping, Tuple

import networkx as nx
import pyqtgraph as pg
from PyQt5.QtCore import QPointF

from sdupy.utils import ignore_errors
from . import register_widget
from ..reactive import reactive_finalizable


@register_widget("pyqtgraph figure")
class PyQtGraphPlot(pg.PlotWidget):
    pass


@register_widget("pyqtgraph view box")
class PyQtGraphViewBox(pg.GraphicsView):
    def __init__(self, parent):
        super().__init__(parent)
        self.item = pg.ViewBox(lockAspect=True)
        self.setCentralItem(self.item)



@register_widget("pyqtgraph plot")
class PgPlot(pg.GraphicsView):
    def __init__(self, parent):
        super().__init__(parent)
        self.item = pg.PlotItem(lockAspect=True)
        self.item.setAspectLocked(True)
        self.setCentralItem(self.item)


def index_to_str(index):
    res = []
    for i in index:
        if isinstance(i, slice):
            res.append("{}:{}".format(i.start if i.start is not None else "", i.stop if i.stop is not None else ""))
        else:
            res.append(str(i))
    return ','.join(res)

@register_widget("pyqtgraph image view")
class PyQtGraphImage(pg.ImageView):
    def __init__(self, parent):
        super().__init__(parent, view=pg.PlotItem())
        self.view.setAspectLocked(True)
        self._show_cursor_proxy = None
        self.cursor_pos_label = None
        self.show_cursor_pos()

    def show_cursor_pos(self, show=True):
        if self._show_cursor_proxy:
            self._show_cursor_proxy.disconnect()
            self._show_cursor_proxy = None
        if self.cursor_pos_label is not None:
            self.removeItem(self.cursor_pos_label)
            self.cursor_pos_label = None

        if show:
            @ignore_errors
            def mouseMoved(evt):
                view_point = self.view.vb.mapSceneToView(evt[0])
                text = "x,y = ({:0.2f}, {:0.2f})".format(view_point.x(), view_point.y())
                if self.image is not None and 'x' in self.axes and 'y' in self.axes:
                    item_point = self.imageItem.mapFromScene(evt[0])
                    ix = int(item_point.x())
                    iy = int(item_point.y())
                    if 0 <= ix < self.image.shape[self.axes['x']] and 0 <= iy < self.image.shape[self.axes['y']]:
                        index = [slice(None, None)] * len(self.image.shape)
                        index[self.axes['x']] = ix
                        index[self.axes['y']] = iy
                        if self.axes.get('t') is not None:
                            index[self.axes['t']] = self.currentIndex
                        val = self.image[tuple(index)]
                        text += "\ndata[{}] = {}".format(index_to_str(index), val)
                self.cursor_pos_label.setText(text)
                if all(isfinite(c) for c in [view_point.x(), view_point.y()]):
                    self.cursor_pos_label.setPos(view_point)
                else:
                    self.cursor_pos_label.setPos(QPointF(0, 0))

            self.cursor_pos_label = pg.TextItem(anchor=(0, 1))
            self.addItem(self.cursor_pos_label)

        self._show_cursor_proxy = pg.SignalProxy(self.scene.sigMouseMoved, rateLimit=60, slot=mouseMoved)

    def dump_state(self):
        return dict(
            #view_state=self.getView().getState(),
            view_state=self.getView().saveState(),
            colormap=self.getHistogramWidget().gradient.saveState(),
            colormap_region=self.getHistogramWidget().region.getRegion()
        )

    def load_state(self, state: dict):
        if 'view_state' in state:
            #self.getView().setState(state['view_state'])
            self.getView().restoreState(state['view_state'])
        if 'colormap' in state:
            self.getHistogramWidget().gradient.restoreState(state['colormap'])
        if 'colormap_region' in state:
            self.getHistogramWidget().region.setRegion(state['colormap_region'])


HOVER_COLOR = 'blue'


@reactive_finalizable
def display_graph2(g: nx.Graph, widget: pg.GraphicsWidget, pos: Mapping[Any, Tuple[float, float]]):
    nodes = list(g)

    def pos_for_node(node):
        return pos[node]

    def text_for_node(node):
        # g.get_no
        return str(node)

    widget.addItem(pg.GraphItem(pos, adj=[[1, 2]], size=1))
    return

    def make_node(node):
        p = pos_for_node(node)
        artist = ax.text(p[0], p[1], text_for_node(node), bbox=dict(boxstyle='square'))
        # patch = mpatches.Ellipse(pos[node], width=10, height=10)
        artist.set_picker(True)
        # patch.node = node
        # patch.autoscale_None()
        # patch.set_transform(mtransforms.IdentityTransform())
        # col = mcollections.PathCollection([patch])
        # col.autoscale_None()
        return artist

    def hover_artist(artist: Artist):
        assert isinstance(artist, Text)
        artist.get_bbox_patch().set_color(HOVER_COLOR)

    def unhover_artist(artist: Artist):
        assert isinstance(artist, Text)
        artist.get_bbox_patch().set_color('red')

    patches = [make_node(node) for node in nodes]

    node_for_artist = {patch: node for node, patch in zip(nodes, patches)}

    hovered_artists = set()

    def on_plot_hover(event: MouseEvent):
        axes = None
        for artist, node in node_for_artist.items():  # type: Tuple[Artist, Any]
            if artist.contains(event)[0]:
                if artist not in hovered_artists:
                    hover_artist(artist)
                    hovered_artists.add(artist)
                    axes = artist.axes
            else:
                if artist in hovered_artists:
                    unhover_artist(artist)
                    hovered_artists.remove(artist)
                    axes = artist.axes
        if axes:
            axes.get_figure().canvas.draw_idle()

    connection_id = ax.figure.canvas.mpl_connect('motion_notify_event', on_plot_hover)

    yield patches, id

    ax.figure.canvas.mpl_disconnect(connection_id)
    for patch in patches:
        patch.remove()
    ax.figure.canvas.draw_idle()
    # , ax.add_collection(PatchCollection(node_collection))
