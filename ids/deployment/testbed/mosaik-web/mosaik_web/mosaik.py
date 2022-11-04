from dateutil import tz
import logging

import arrow
import mosaik_api
import networkx as nx

from mosaik_web import server
from simpy.io.base import BaseSSLSocket


logger = logging.getLogger('mosaik_web.mosaik')

meta = {
    'type': 'time-based',
    'models': {
        'Topology': {
            'public': True,
            'params': [],
            'attrs': [],
            'any_inputs': True,
        },
    },
    'extra_methods': [
        'set_config',
        'set_etypes',
    ],
}

# TODO: Document config file format
default_config = {
    'ignore_types': ['Topology'],
    'merge_types': ['Branch', 'Transformer'],
    'disable_heatmap': False,
    'timeline_hours': 24,
    'etypes': {},
}

DATE_FORMAT = 'YYYY-MM-DD HH:mm:ss'


class MosaikWeb(mosaik_api.Simulator):
    def __init__(self):
        super().__init__(meta)
        self.start_date = None
        self.step_size = None
        self.server = None
        self.sid = None
        self.eid = None
        self.config = default_config

        self.time_resolution = None
        self.server_addrs = None
        self.backend = None
        self.env = None
        self.activate_ssl = None

    def configure(self, args, backend, env):
        """Start a wevserver for the visualization."""
        self.server_addr = mosaik_api._parse_addr(args['--serve'])
        self.backend = backend
        self.env = env

    def init(self, sid, start_date, time_resolution, step_size, activate_ssl=False, keyfile=None, certfile=None):
        self.time_resolution = float(time_resolution)
        if self.time_resolution != 1.0:
            print('WARNING: %s got a time_resolution other than 1.0, which \
                   can not be handled by this simulator.', sid)

        self.sid = sid
        dt = arrow.parser.DateTimeParser().parse(start_date, DATE_FORMAT)
        self.start_date = arrow.get(dt, tz.tzlocal()).isoformat()
        self.step_size = step_size

        self.activate_ssl = activate_ssl
        if not self.activate_ssl:
            server_sock = self.backend.TCPSocket.server(self.env, self.server_addr)
        else:
            server_sock = BaseSSLSocket(self.env, keyfile=keyfile, certfile=certfile)
            server_sock.bind(self.server_addr)
            server_sock.listen(5)

        self.server = server.Server(self.env, server_sock, activate_ssl=self.activate_ssl)

        return self.meta

    def create(self, num, model):
        if num != 1 or self.eid is not None:
            raise ValueError('Can only one grid instance.')
        if model != 'Topology':
            raise ValueError('Unknown model: "%s"' % model)

        self.eid = 'topo'

        return [{'eid': self.eid, 'type': model, 'rel': []}]

    def step(self, time, inputs, max_advance):
        inputs = inputs[self.eid]

        if not self.server.topology:
            yield from self._build_topology()

        progress = yield self.mosaik.get_progress()

        etype_conf = self.config['etypes']
        node_data = {}
        for node in self.server.topology['nodes']:
            node_id = node['name']
            try:
                attr = etype_conf[node['type']]['attr']
            except KeyError:
                val = 0
            else:
                # val = data[node_id][attr]
                val = inputs[attr][node_id]
            node_data[node_id] = {
                'value': val,
            }
        self.server.set_new_data(time, progress, node_data)

        return time + self.step_size

    def set_config(self, cfg=None, **kwargs):
        if cfg is not None:
            self.config.update(cfg)
        self.config.update(**kwargs)

    def set_etypes(self, etype_conf):
        self.config['etypes'].update(etype_conf)

    def _build_topology(self):
        """Get all related entities, create the topology and set it to the
        web server."""
        logger.info('Creating topology ...')

        data = yield self.mosaik.get_related_entities()
        nxg = nx.Graph()
        nxg.add_nodes_from(data['nodes'].items())
        nxg.add_edges_from(data['edges'])

        # Required for get_data() calls.
        full_id = '%s.%s' % (self.sid, self.eid)
        self.related_entities = [(e, nxg.nodes[e]['type'])
                                 for e in nxg.neighbors(full_id)]

        self._clean_nx_graph(nxg)
        self.server.topology = self._make_d3js_topology(nxg)
        self.server.topology_ready.succeed()

        logger.info('Topology created')

    def _clean_nx_graph(self, nxg):
        """Remove and merge nodes and edges according to ``self.ignore_types``
        and ``self.merge_types``."""
        nxg.remove_nodes_from([n for n, d in nxg.nodes.items()
                               if d['type'] in self.config['ignore_types']])
        for node in [n for n, d in nxg.nodes.items()
                     if d['type'] in self.config['merge_types']]:
            new_edge = nxg.neighbors(node)

            # unroll key iterator
            new_edge = [key for key in new_edge]

            assert len(new_edge) == 2, new_edge
            nxg.remove_node(node)
            nxg.add_edge(*new_edge)

    def _make_d3js_topology(self, nxg):
        """Create the topology for D3JS."""
        # We have to use two loops to make sure "node_idx" is filled for the
        # second one.
        topology = {
            'start_date': self.start_date,
            'update_interval': self.step_size,
            'timeline_hours': self.config['timeline_hours'],
            'disable_heatmap': self.config['disable_heatmap'],
            'etypes': self.config['etypes'],
            'nodes': [],
            'links': [],
        }
        node_idx = {}

        for node, attrs in nxg.nodes.items():
            node_idx[node] = len(topology['nodes'])
            type = attrs['type']
            topology['nodes'].append({
                'name': node,
                'type': type,
                'value': 0,
            })

        for source, target in nxg.edges():
            topology['links'].append({
                'source': node_idx[source],
                'target': node_idx[target],
                'length': 0,  # TODO: Add eddge data['length'],
            })

        return topology


def main():
    desc = 'Simple visualization for mosaik simulations'
    extra_opts = [
        '-s HOST:PORT, --serve=HOST:PORT    ',
        ('            Host and port for the webserver '
         '[default: 127.0.0.1:8000]'),
    ]
    mosaik_api.start_simulation(MosaikWeb(), desc, extra_opts)
