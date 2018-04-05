from typing import Any, Callable, Iterable, Mapping, Sequence, Set, Tuple, overload

import networkx
import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QBrush, QColor, QFont
from pyqtgraph import SpotItem

from sdupy import reactive, reactive_finalizable
from sdupy.reactive import unwrapped
from sdupy.utils import ignore_errors


@overload
def make_node(
        edges: Sequence[Any],
        pos: Tuple[float, float] = None,
        face_color: Tuple[float, float, float] = None,
        size: float = None,
        on_mouse_event: Callable = None,
        label: str = None,
) -> dict:
    pass


@reactive
def make_node(**kwargs):
    return dict(**kwargs)


@reactive_finalizable
def _draw_graph(nodes: Mapping[Any, dict], edges: Sequence[dict], widget=None):
    widget.item.setAspectLocked()
    graph_item = pg.GraphItem()
    widget.item.addItem(graph_item)
    print("redrawing graph")
    key_for_index = list(nodes.keys())
    index_for_key = {key: index for index, key in enumerate(key_for_index)}
    spots = []
    adj = []
    brushes = []
    datas = []

    # edges
    for edge in edges:
        adj.append([index_for_key[edge['src']], index_for_key[edge['dst']]])
    for index, key in enumerate(key_for_index):
        node = nodes[key]
        for neigh in node.get('edges', []):
            adj.append([index, index_for_key[neigh]])

    # positions
    if not all(('pos' in node for node in nodes.values())):
        g = networkx.Graph()
        g.add_nodes_from(nodes.keys())
        g.add_edges_from(adj)
        positions = networkx.spring_layout(g)
        for key, node in nodes.items():
            node['pos'] = positions[key]

    positions = []

    for index, key in enumerate(key_for_index):
        node = nodes[key]
        # {'pos': (x, y), 'size', 'pen', 'brush', 'symbol'}
        spot = dict()
        datas.append((key, node))
        node_pos = node.get('pos')
        spot['pos'] = node_pos
        positions.append(node_pos)

        if 'qt_pen' in node:
            spot['pen'] = node['qt_pen']
        if 'qt_brush' in node:
            spot['brush'] = node['qt_brush']
        if 'size' in node:
            spot['size'] = node['size']
        # spot['brush'] = node_pos
        # spot['symbol'] = node_pos

        spots.append(spot)

        if 'face_color' in node:
            brushes.append(QBrush(QColor(*node['face_color'])))
        else:
            brushes.append(None)

    print('adj', adj)
    graph_item.setData(spots=spots,
                       pos=np.array(positions),
                       adj=np.array(adj) if len(adj) > 0 else np.ndarray(shape=(0, 2), dtype=int),
                       data=datas,
                       pxMode=True)
    widget.item.addItem(graph_item)

    labels = []
    for node in nodes.values():
        if 'label' in node:
            label = pg.TextItem(text=node['label'], anchor=(0.5, 0.5))
            label.setPos(QPointF(*node['pos']))
            widget.item.addItem(label)
            labels.append(label)
            pass

    yield graph_item

    widget.item.removeItem(graph_item)
    for label in labels:
        graph_item.item.removeItem(label)


@reactive_finalizable
def _draw_labels(nodes: Mapping[Any, dict], widget=None):
    items = []
    for node in nodes.values():
        if 'label' in node:
            text = pg.TextItem(text=node['label'], anchor=node['pos'])
            text.setFont(QFont('Times', 1))
            widget.item.addItem(text)
            # item.anchor((0, 0), node['pos'])
            items.append(text)

    yield items
    for text in items:
        widget.item.removeItem(text)


cnt = 0


@reactive_finalizable(pass_args=['nodes', 'edges'])
def graph(nodes: Mapping[Any, dict], edges: Sequence[dict] = [],
          widget=None, mouse_events: Set[str] = {'click'}, on_mouse_event: Callable = None):
    """

    :param nodes:
    :param widget:
    :param mouse_events: A subset of: 'press', 'release', 'click', 'dbl_click', 'move', 'enter', 'exit'
    :return:
    """
    mouse_events = set(mouse_events)
    graph_item = _draw_graph(nodes, edges, widget)
    # labels = _draw_labels(nodes, widget)
    print("nodes", nodes)
    use_move = {'move'} & mouse_events
    use_enter = {'enter'} & mouse_events
    use_exit = {'exit'} & mouse_events
    omm = None
    global cnt
    ccc = cnt

    if use_move or use_enter or use_exit:
        inside_keys = set()  # spots that we're inside
        cnt += 1

        @ignore_errors
        def on_mouse_move(p: QPointF):
            print("omm", ccc)
            raw_nodes = unwrapped(nodes)
            spots = unwrapped(graph_item).scatter.pointsAt(widget.item.mapToView(p))  # type: Iterable[SpotItem]
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

        widget.enableMouse(False)
        omm = on_mouse_move
        widget.sigSceneMouseMoved.connect(omm)
        # widget.sigSceneMouseMoved.disconnect(omm)
        # finalizers.append(lambda: widget.sigSceneMouseMoved.disconnect(connection))

    yield graph_item
    print("disconnect", ccc, omm)
    if omm:
        widget.sigSceneMouseMoved.disconnect(omm)

    # del labels  # just show we used it
