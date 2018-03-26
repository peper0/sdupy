# region init
# below


import logging
from typing import Any, Callable, Iterable, Mapping, Sequence, Set, Tuple, overload

import networkx as nx
import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QBrush, QColor
from pyqtgraph import SpotItem

import sdupy
from sdupy import reactive, reactive_finalizable, var
from sdupy.reactive import unwrapped
from sdupy.utils import ignore_errors
from sdupy.widgets import PyQtGraphPlot
from sdupy.widgets.pyqtgraph import PyQtGraphViewBox

# ax = sdupy.unwrap(sdupy.axes("gr4"))

w = sdupy.window().obtain_widget('vb2', PyQtGraphViewBox)


@overload
def make_node(
        edges: Sequence[Any],
        pos: Tuple[float, float] = None,
        face_color: Tuple[float, float, float] = None,
        size: float = None,
        on_mouse_event: Callable = None,
) -> dict:
    pass


@reactive
def make_node(**kwargs):
    return dict(**kwargs)


# widget.addItem(pg.GraphItem(pos, adj=[[1, 2]], size=1))
# widget.addItem(pg.GraphItem(pos, adj=[[1, 2]], size=1))
@reactive_finalizable
def display_graph3(nodes: Mapping[Any, dict], edges: Sequence[dict], widget=None):
    key_for_index = list(nodes.keys())
    index_for_key = {key: index for index, key in enumerate(key_for_index)}
    spots = []
    adj = []
    pos = []
    brushes = []
    datas = []
    for index, key in enumerate(key_for_index):
        node = nodes[key]
        # {'pos': (x, y), 'size', 'pen', 'brush', 'symbol'}
        spot = dict()
        datas.append((key, node))
        node_pos = node.get('pos')
        assert node_pos is not None, 'auto positioning not implemented yet'
        spot['pos'] = node_pos
        pos.append(node_pos)

        if 'qt_pen' in node:
            spot['pen'] = node['qt_pen']
        if 'qt_brush' in node:
            spot['brush'] = node['qt_brush']
        if 'size' in node:
            spot['size'] = node['size']
        # spot['brush'] = node_pos
        # spot['symbol'] = node_pos

        spots.append(spot)
        for neigh in node.get('edges', []):
            adj.append([index, index_for_key[neigh]])
        if 'face_color' in node:
            brushes.append(QBrush(QColor(*node['face_color'])))
        else:
            brushes.append(None)

    for edge in edges:
        adj.append([index_for_key[edge['src']], index_for_key[edge['dst']]])
    print('adj', adj)
    graph_item = pg.GraphItem(spots=spots,
                              pos=np.array(pos),
                              adj=np.array(adj) if len(adj) > 0 else np.ndarray(shape=(0, 2), dtype=int),
                              data=datas)
    widget.item.addItem(graph_item)

    yield graph_item

    widget.item.removeItem(graph_item)


cnt = 0


@reactive_finalizable(pass_args=['nodes', 'edges'])
def display_graph2(nodes: Mapping[Any, dict], edges: Sequence[dict] = [],
                   widget=None, mouse_events: Set[str] = {'click'}, on_mouse_event: Callable = None):
    """

    :param nodes:
    :param widget:
    :param mouse_events: A subset of: 'press', 'release', 'click', 'dbl_click', 'move', 'enter', 'exit'
    :return:
    """
    mouse_events = set(mouse_events)
    graph_item = display_graph3(nodes, edges, widget)
    print("nodes", nodes)
    use_move = {'move'} & mouse_events
    use_enter = {'enter'} & mouse_events
    use_exit = {'exit'} & mouse_events
    if use_move or use_enter or use_exit:
        inside_keys = set()  # spots that we're inside
        global cnt
        ccc = cnt
        cnt += 1

        @ignore_errors
        def on_mouse_move(p: QPointF):
            print("omm", ccc)
            raw_nodes = unwrapped(nodes)
            spots = unwrapped(graph_item).scatter.pointsAt(w.item.mapToView(p))  # type: Iterable[SpotItem]
            new_inside_keys = set(spot.data()[0] for spot in spots)
            if on_mouse_event is not None:
                on_mouse_event(type='move', keys=new_inside_keys)
            for key in new_inside_keys:
                node = raw_nodes.get(key)
                if node is not None:
                    node_on_mouse_event = node.get('on_mouse_event')
                    print('on_mouse_event', node_on_mouse_event)
                    if node_on_mouse_event:
                        if use_move:
                            node_on_mouse_event(type='move')  # fixme: more
                        if use_enter:
                            if key not in inside_keys:
                                inside_keys.add(key)
                                node_on_mouse_event(type='enter')

            exited_keys = inside_keys - new_inside_keys
            for key in exited_keys:
                node = raw_nodes.get(key)
                assert node is not None
                inside_keys.remove(key)
                if use_exit:
                    node_on_mouse_event = node.get('on_mouse_event')
                    if node_on_mouse_event:
                        if key not in inside_keys:
                            node_on_mouse_event(type='exit')

        widget.enableMouse(True)
        omm = on_mouse_move
        widget.sigSceneMouseMoved.connect(omm)
        # widget.sigSceneMouseMoved.disconnect(omm)
        # finalizers.append(lambda: widget.sigSceneMouseMoved.disconnect(connection))

    yield graph_item
    print("disconnect", ccc, omm)
    widget.sigSceneMouseMoved.disconnect(omm)


selected_nodes = var(set())


@reactive
def calc_size(node, selected_nodes=selected_nodes):
    return 20 if node in selected_nodes else 10


def handle_mouse(node_key):
    @ignore_errors
    def on_mouse_event(type, **kwargs):
        # print('type', type, node_key)
        if type == 'enter':
            print("add", node_key)
            selected_nodes.__inner__.add(node_key)
            selected_nodes.__notifier__.notify_observers()
        elif type == 'exit':
            print("del", node_key)
            selected_nodes.__inner__.remove(node_key)
            selected_nodes.__notifier__.notify_observers()

    return on_mouse_event


vv = var(4)

vv += 1

g = nx.random_geometric_graph(500, 0.125)
nodes = {i: make_node(pos=pos) for i, pos in nx.get_node_attributes(g, 'pos').items()}
edges = [dict(src=src, dst=dst) for src, dst in g.edges]
edges
tt = display_graph2(widget=w, nodes=nodes, edges=edges, mouse_events={'move', 'enter', 'exit'})
# tt = display_graph2(widget=w, nodes=make_dict(
#     a=make_node(pos=(0, 10), size=calc_size('a'), edges=['b', 'c'],
#                 on_mouse_event=handle_mouse('a')),
#     b=make_node(pos=make_tuple(vv, 20), size=calc_size('b'), edges=[], on_mouse_event=handle_mouse('b')),
#     c=make_node(pos=(10, 10), size=calc_size('c'), edges=[], on_mouse_event=handle_mouse('c')),
# ), mouse_events={'move', 'enter', 'exit'})

# endregion


logging.error("ojoj")

w2 = sdupy.window().obtain_widget('pl', PyQtGraphPlot)  # type: PyQtGraphPlot

g = nx.random_geometric_graph(200, 0.125)
pos2 = nx.get_node_attributes(g, 'pos')
# tt = display_graph2(g, widget=w.item, pos=pos)
# tt = display_graph2(g, widget=w2, pos=pos)
# list(g.edges)
adj = np.array(list(g.edges))
pos = np.array(list(pos2.values()))
spots = [dict(pos=p) for p in pos]
item = pg.GraphItem(spots=spots, adj=adj, size=20)
w.item.addItem(item)
item.scatter.sigClicked.connect(lambda *kwargs: print("click: ", kwargs))

highlighted = set()


def on_move(p: QPointF):
    nodes = item.scatter.pointsAt(w.item.mapToView(p))
    for node in highlighted:
        node.setBrush(QBrush(QColor(0, 0, 255)))

    highlighted.clear()
    for node in nodes:  # type: SpotItem
        node.setBrush(QBrush(QColor(255, 0, 0)))
        highlighted.add(node)
    # print(node)


# w.item.mapToView(QPointF(100, 100))
# item.scatter.pointsAt(QPointF(0.0, 0.0))
# pp = item.scatter.points()[0]
# pp.setBrush(QBrush(QColor(255, 0, 0)))

w.enableMouse(True)
w.sigSceneMouseMoved.connect(on_move)
# tt = display_graph(g, ax=ax, pos=nx.circular_layout(g, scale=100))

pg.plot([1, 2, 3, 2, 1], pen='r')  # data can be a list of values or a numpy array
win = pg.GraphicsWindow()
win.addPlot([1, 2, 3, 3, 2, 3, 1], row=0)

g = nx.Graph()
g.add_node(1)
g.add_node('yy')
# nx.draw_networkx(g, with_labels=True, ax=sdupy.unwrap(sdupy.axes("gr")), pos=nx.circular_layout(g))
g.add_cycle([1, 2, 3, 4])
g.add_cycle([1, 2, 6, 7, 8, 9])
list(nx.all_shortest_paths(g, 1, 2))
g.nodes[2]
nx.non_edges(g)
nx.info(g)
nx.set_node_attributes(g, 1, a=4)
g2 = nx.hypercube_graph(3)
r = nx.draw_networkx_nodes(g, ax=sdupy.unwrap(sdupy.axes("gr2")), pos=nx.circular_layout(g))
e = nx.draw_networkx_edges(g, ax=sdupy.unwrap(sdupy.axes("gr2")), pos=nx.circular_layout(g))
l = nx.draw_networkx_labels(g, ax=sdupy.unwrap(sdupy.axes("gr2")), pos=nx.circular_layout(g))
r.set_picker(True)

# col = ax.scatter(x, y, 100 * s, c, picker=True)
# fig.savefig('pscoll.eps')

import pyqtgraph.examples

pyqtgraph.examples.run()

"""
import json
%matplotlib qt5
"""

G = nx.erdos_renyi_graph(30, 4.0 / 30)
while not nx.is_connected(G):
    G = nx.erdos_renyi_graph(30, 4.0 / 30)
plt.figure(figsize=(6, 4))
nx.draw(G)
pos = nx.drawing.spring_layout(G)  # default to spring layout
node_collection = nx.draw_networkx_nodes(G, pos)
edge_collection = nx.draw_networkx_edges(G, pos)

for ix, deg in G.degree():
    G.node[ix]['degree'] = deg
    G.node[ix]['parity'] = (1 - deg % 2)

for ix, katz in nx.katz_centrality(G).items():
    G.node[ix]['katz'] = katz

G.nodes(data=True)

from __future__ import print_function
import matplotlib.pyplot as plt
from numpy.random import rand

if 1:  # picking on a scatter plot (matplotlib.collections.RegularPolyCollection)

    x, y, c, s = rand(4, 100)


    def onpick3(event):
        ind = event.ind
        print('onpick3 scatter:', ind, np.take(x, ind), np.take(y, ind))


    fig, ax = plt.subplots()
    col = ax.scatter(x, y, 100 * s, c, picker=True)
    # fig.savefig('pscoll.eps')
    fig.canvas.mpl_connect('pick_event', onpick3)

if 1:  # picking images (matplotlib.image.AxesImage)
    fig, ax = plt.subplots()
    im1 = ax.imshow(rand(10, 5), extent=(1, 2, 1, 2), picker=True)
    im2 = ax.imshow(rand(5, 10), extent=(3, 4, 1, 2), picker=True)
    im3 = ax.imshow(rand(20, 25), extent=(1, 2, 3, 4), picker=True)
    im4 = ax.imshow(rand(30, 12), extent=(3, 4, 3, 4), picker=True)
    ax.axis([0, 5, 0, 5])


    def onpick4(event):
        artist = event.artist
        if isinstance(artist, AxesImage):
            im = artist
            A = im.get_array()
            print('onpick4 image', A.shape)


    fig.canvas.mpl_connect('pick_event', onpick4)

plt.show()
