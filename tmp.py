# region init
# below


import networkx as nx

import sdupy
from sdupy import reactive, var
from sdupy.reactive.notifier import all_notifiers, stats_for_notify_func
from sdupy.utils import ignore_errors
from sdupy.vis.graph import graph, make_node
from sdupy.widgets import PgPlot

# ax = sdupy.unwrap(sdupy.axes("gr4"))

sdupy.window('graph')
w = sdupy.window().obtain_widget('vb3', PgPlot)

# widget.addItem(pg.GraphItem(pos, adj=[[1, 2]], size=1))
# widget.addItem(pg.GraphItem(pos, adj=[[1, 2]], size=1))


cnt = 0

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

g = nx.random_geometric_graph(10, 0.02)
nodes = {i: make_node(pos=(pos[0] * 1000, pos[1] * 1000), on_mouse_event=handle_mouse(i), label='hej\nwajha')
         for i, pos in nx.get_node_attributes(g, 'pos').items()}
edges = [dict(src=src, dst=dst) for src, dst in g.edges]
w.item = w.plotItem
tt = graph(widget=w, nodes=nodes, edges=edges, mouse_events={'move', 'enter', 'exit'})
# tt = display_graph2(widget=w, nodes=make_dict(
#     a=make_node(pos=(0, 10), size=calc_size('a'), edges=['b', 'c'],
#                 on_mouse_event=handle_mouse('a')),
#     b=make_node(pos=make_tuple(vv, 20), size=calc_size('b'), edges=[], on_mouse_event=handle_mouse('b')),
#     c=make_node(pos=(10, 10), size=calc_size('c'), edges=[], on_mouse_event=handle_mouse('c')),
# ), mouse_events={'move', 'enter', 'exit'})
import gc

gc.collect()
# endregion

notifier_nodes = {}
nf_nodes = {}

for notifier in list(all_notifiers):
    notifier_nodes[notifier] = make_node(
        label='{}\nprio={}\ncalls={}'.format(
            notifier.name,
            notifier.priority,
            notifier.calls
        ),
        edges=[nf for nf, _observer in notifier._observers.items()]
    )

for nf, stats in list(stats_for_notify_func.items()):
    nf_nodes[nf] = make_node(
        label='{}\ncalls={}\nexception={}'.format(
            stats.get('name'),
            stats.get('calls'),
            stats.get('exception')
        )
    )

nodes2 = dict()
nodes2.update(notifier_nodes)
nodes2.update(nf_nodes)

w2 = sdupy.window().obtain_widget('notifications', PgPlot)
w2.item = w2.plotItem
ttt = graph(widget=w2, nodes=nodes2)

# notifier: observers, priority, num notifications
# observer: notifiers, priority, num notifications, time spent?

sdupy.run_mainloop()
