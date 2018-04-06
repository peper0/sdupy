from typing import Any, Mapping, Tuple

import networkx as nx
import pyqtgraph as pg

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

@register_widget("pyqtgraph image view")
class PyQtGraphImage(pg.ImageView):
    def __init__(self, parent):
        super().__init__(parent)
        self.view.setAspectLocked(True)
        #self.item = pg.ViewBox()
        #self.setCentralItem(self.item)

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
