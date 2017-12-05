#!/usr/bin/env python

from __future__ import print_function

import requests
import json
import logging
import pkgutil
import argparse
import sys
import os
import collections

import definitions
import local_definitions

try:
    import configparser  # Python 3
except ImportError:
    import ConfigParser as configparser  # Python 2

__version__ = '0.1.0'  # also in setup.py

if sys.version_info[:2] <= (2, 7):
    # Python 2
    get_input = raw_input
else:
    # Python 3
    get_input = input

GRAPH_URL = "https://graph.facebook.com"

log = logging.getLogger(__name__)


def load_definition(definition_package):
    """
    Returns a map of node_types to importers loaded from a package.
    """
    definition_importers = {}
    for importer, modname, _ in pkgutil.iter_modules(definition_package.__path__):
        definition_importers[modname] = importer
    return definition_importers


# Map of node type names to importers
definition_importers = {}
# Load node_types
definition_importers.update(load_definition(definitions))
# Override with local_node_types
definition_importers.update(load_definition(local_definitions))


def load_keys(args):
    """
    Get the Facebook API keys. Order of precedence is command line,
    environment, config file.
    """
    app_id = args.app_id
    app_secret = args.app_secret
    env = os.environ.get
    if not app_id:
        app_id = env('APP_ID')
    if not app_secret:
        app_secret = env('APP_SECRET')

    if args.config and not (app_id and app_secret):
        credentials = load_config(args)
        if credentials:
            app_id = credentials['app_id']
            app_secret = credentials['app_secret']
        else:
            app_id, app_secret = input_keys(args)
    return app_id, app_secret


def load_config(args):
    path = args.config
    profile = args.profile
    if not os.path.isfile(path):
        return {}

    config = configparser.ConfigParser()
    config.read(path)
    data = {}
    for key in ['app_id', 'app_secret']:
        try:
            data[key] = config.get(profile, key)
        except configparser.NoSectionError:
            sys.exit("no such profile %s in %s" % (profile, path))
        except configparser.NoOptionError:
            sys.exit("missing %s from profile %s in %s" % (
                key, profile, path))
    return data


def save_config(args, app_id, app_secret):
    if not args.config:
        return
    config = configparser.ConfigParser()
    config.add_section(args.profile)
    config.set(args.profile, 'app_id', app_id)
    config.set(args.profile, 'app_secret', app_secret)

    with open(args.config, 'w') as config_file:
        config.write(config_file)


def input_keys(args):
    print("Please enter Facebook API credentials")

    config = load_config(args)

    def i(name):
        prompt = name.replace('_', ' ')
        if name in config:
            prompt += ' [%s]' % config[name]
        return get_input(prompt + ": ") or config.get(name)

    app_id = i('app_id')
    app_secret = i('app_secret')
    save_config(args, app_id, app_secret)
    return app_id, app_secret


def main():
    parser = get_argparser()
    args = parser.parse_args()

    logging.basicConfig(
        filename=args.log,
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )

    if args.command is None:
        parser.print_help()
        sys.exit(1)
    elif args.command == 'configure':
        input_keys(args)
    elif args.command == 'url':
        fb = Fbarc()
        print(fb.generate_url(args.node, args.definition, escape=args.escape))
    else:
        # Load keys
        app_id, app_secret = load_keys(args)
        fb = Fbarc(app_id=app_id, app_secret=app_secret)
        if args.command == 'metadata':
            print_graph(fb.get_metadata(args.node), pretty=args.pretty)
        elif args.command == 'search':
            print_graph(fb.search(args.node_type, args.query))
        else:
            definition_name = args.definition
            if definition_name == 'discover':
                definition_name = fb.discover_type(args.node)

            print_graphs(fb.get_nodes(args.node, definition_name, levels=args.levels,
                                      exclude_definition_names=args.exclude), pretty=args.pretty)


def print_graph(graph, pretty=False):
    print(json.dumps(graph, indent=4 if pretty else None))


def print_graphs(graph_iter, pretty=False):
    for graph in graph_iter:
        print_graph(graph, pretty)


def get_argparser():
    """
    Get the command line argument parser.
    """

    config = os.path.join(os.path.expanduser("~"), ".fbarc")

    parser = argparse.ArgumentParser("fbarc")
    parser.add_argument('-v', '--version', action='version', version='%(prog)s {}'.format(__version__))
    parser.add_argument('--debug', action='store_true')
    parser.add_argument("--log", dest="log",
                        default="fbarc.log", help="log file")
    parser.add_argument("--app_id",
                        default=None, help="Facebook app id")
    parser.add_argument("--app_secret",
                        default=None, help="Facebook app secret")
    parser.add_argument('--config', default=config,
                        help="Config file containing Facebook keys")
    parser.add_argument('--profile', default='main',
                        help="Name of a profile in your configuration file")

    # Subparsers
    subparsers = parser.add_subparsers(dest='command', help='command help')

    subparsers.add_parser('configure', help='input API credentials and store in configuration file')

    graph_parser = subparsers.add_parser('graph', help='retrieve nodes from the Graph API')
    definition_choices = ['discover']
    definition_choices.extend(definition_importers.keys())

    graph_parser.add_argument('definition', choices=definition_choices,
                              help='definition to use to retrieve the node. discover will discover node type '
                                   'from API.')
    graph_parser.add_argument('node', help='identify node to retrieve by providing node id, username, or Facebook URL')
    graph_parser.add_argument('--levels', type=int, default='1',
                              help='number of levels of nodes to retrieve (default=1)')
    graph_parser.add_argument('--exclude', nargs='+', choices=list(definition_importers.keys()),
                              help='node type definitions to exclude from recursive retrieval', default=[])
    graph_parser.add_argument('--pretty', action='store_true', help='pretty print output')

    metadata_parser = subparsers.add_parser('metadata', help='retrieve metadata for a node from the Graph API')
    metadata_parser.add_argument('node', help='identify node to retrieve by providing node id, username, or Facebook '
                                              'URL')
    metadata_parser.add_argument('--pretty', action='store_true', help='pretty print output')

    url_parser = subparsers.add_parser('url', help='generate the url to retrieve the node from the Graph API')
    url_parser.add_argument('definition', choices=list(definition_importers.keys()),
                            help='definition to use to retrieve the node.')
    url_parser.add_argument('node', help='identify node to retrieve by providing node id or username')
    url_parser.add_argument('--escape', action='store_true', help='escape the characters in the url')

    subparsers.add_parser('configure', help='input API credentials and store in configuration file')

    return parser


class Fbarc(object):
    def __init__(self, app_id=None, app_secret=None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = None

        # Map of node types definition names to node type definitions
        self._definitions = {}

    def generate_url(self, node_id, definition_name, escape=False):
        """
        Returns the url for retrieving the specified node from the Graph API
        given the node type definition.
        """
        url, params = self._prepare_request(node_id, definition_name)
        if not escape:
            return '{}?{}'.format(url, '&'.join(['{}={}'.format(k, v) for k, v in params.items()]))
        else:
            return requests.Request('GET', url, params=params).prepare().url

    def get_nodes(self, root_node_id, root_definition_name, levels=1,
                  exclude_definition_names=None):
        """
        Iterator for getting nodes, starting with the root node and proceeding
        for the specified number of levels of connected nodes.
        """
        node_queue = collections.deque()
        node_queue.appendleft((root_node_id, root_definition_name, 1))
        retrieved_nodes = set()
        while node_queue:
            node_id, definition_name, level = node_queue.popleft()
            log.debug('Popped %s (%s) of the node queue (level %s). %s nodes left on the node queue.',
                      node_id, definition_name, level, len(node_queue))
            if node_id not in retrieved_nodes:
                if definition_name is None or definition_name not in exclude_definition_names:
                    node_graph = self.get_node(node_id, definition_name)
                    if level < levels:
                        connected_nodes = self.find_connected_nodes(definition_name, node_graph,
                                                                    default_only=False)
                        log.debug("%s connected nodes found in %s and added to node queue.", len(connected_nodes),
                                  node_id)
                        for connected_node_id, connected_definition_name in connected_nodes:
                            node_queue.append((connected_node_id, connected_definition_name, level + 1))
                    retrieved_nodes.add(node_id)
                    yield node_graph
                else:
                    log.debug('%s is an excluded node type definition (%s), so skipping.',
                              node_id, definition_name)
            else:
                log.debug('%s has already been retrieved, so skipping.', node_id)

    def get_node(self, node_id, definition_name):
        """
        Gets a node graph as specified by the node type definition.
        """
        log.info("Getting node %s (%s)", node_id, definition_name)
        url, params = self._prepare_request(node_id, definition_name)
        return self._perform_http_get(url, params=params, paging=True)

    def get_page(self, page_link, graph_fragment):
        """
        Retrieve a page specified by a page link and append to graph fragment.

        The page graph fragment is searched for additional result pages and returned
        as a list of (page link, graph fragment).

        A page graph fragment will look like:
        {
            "data": [
                {
                    "id": "10158607823500725",
                    "link": "https://www.facebook.com/DonaldTrump/photos/a.488852220724.393301.153080620724/10158607823500725/?type=3"
                },
                ....
            ],
            "paging": {
                "cursors": {
                    "before": "MTAxNTg2MDc4MjM1MDA3MjUZD",
                    "after": "MTAxNTg1NTQzNTcxMjA3MjUZD"
                },
                "next": "https://graph.facebook.com/v2.8/488852220724/photos?access_token=EAACEdEose0cBABNVIWZAPVEKXBRk4OVdniVZCHpQV1yZAKhKWh4FxEGo4C3HOQVCW47Ks0z0zdTn96yxqVux2Sv045dh6ZC9R8CpriRfwppGZAltRaGaiyk1Ucr0hdc7DUNAIaSGv9U5ZBHh1u3gb9k3a1tv8OyrPTyQpcStN1Drz24sAXOgZB5PdWSSEoYQAseseVGt4IyFgZDZD&pretty=0&fields=id%2Clink&limit=25&after=MTAxNTg1NTQzNTcxMjA3MjUZD",
                "previous": "https://graph.facebook.com/v2.8/488852220724/photos?access_token=EAACEdEose0cBABNVIWZAPVEKXBRk4OVdniVZCHpQV1yZAKhKWh4FxEGo4C3HOQVCW47Ks0z0zdTn96yxqVux2Sv045dh6ZC9R8CpriRfwppGZAltRaGaiyk1Ucr0hdc7DUNAIaSGv9U5ZBHh1u3gb9k3a1tv8OyrPTyQpcStN1Drz24sAXOgZB5PdWSSEoYQAseseVGt4IyFgZDZD&pretty=0&fields=id%2Clink&limit=25&before=MTAxNTg2MDc4MjM1MDA3MjUZD"
            }
        }

        """
        log.debug("Getting page link: %s.", page_link)
        page_fragment = requests.get(page_link).json()

        pages = []
        # Look for paging in root of this graph fragment
        if 'paging' in page_fragment and 'next' in page_fragment['paging']:
            pages.append((page_fragment['paging']['next'], graph_fragment))

        # Look for additional paging links.
        pages.extend(self.find_paging_links(page_fragment['data']))
        # Append data to graph location
        graph_fragment.extend(page_fragment['data'])

        return pages

    def get_metadata(self, node_id):
        """
        Retrieve the metadata for a node.
        """
        return self._perform_http_get(self._prepare_url(node_id), params={'metadata': 1})

    def discover_type(self, node_id):
        """
        Look up the type of a node.
        """
        return self.get_metadata(node_id)['metadata']['type']

    def _prepare_request(self, node_id, definition_name):
        """
        Prepare the request url and params.

        The access token is not included in the params.
        """
        params = {
            'metadata': 1,
            'fields': self._prepare_field_param(definition_name, default_only=False)
        }
        return self._prepare_url(node_id), params

    @staticmethod
    def _prepare_url(node_id):
        """
        Prepare a request url.
        """
        return "{}/{}".format(GRAPH_URL, node_id)

    def _prepare_field_param(self, definition_name, default_only=True):
        """
        Construct the fields parameter.
        """
        definition = self._get_definition(definition_name)
        fields = []
        if not default_only:
            fields.append('metadata{type}')
        fields.extend(definition.default_fields)
        if not default_only:
            fields.extend(definition.fields)
        for edge in definition.default_edges:
            fields.append(
                '{}{{{}}}'.format(edge, self._prepare_field_param(definition.get_edge_type(edge))))
        if not default_only:
            for edge in definition.edges:
                fields.append(
                    '{}{{{}}}'.format(edge, self._prepare_field_param(definition.get_edge_type(edge))))
        if 'id' not in fields:
            fields.insert(0, 'id')
        return ','.join(fields)

    def find_connected_nodes(self, definition_name, graph_fragment, default_only=True):
        """
        Returns a list of (node ids, definition names) found in a graph fragment.
        """
        connected_nodes = []
        definition = self._get_definition(definition_name)
        # Get the connections from the definition.
        edges = list(definition.default_edges)
        if not default_only:
            edges.extend(definition.edges)
        for edge in edges:
            if definition.should_follow_edge(edge):
                edge_type = definition.get_edge_type(edge)
                if edge in graph_fragment:
                    if 'data' in graph_fragment[edge]:
                        for node in graph_fragment[edge]['data']:
                            connected_nodes.append((node['id'], edge_type))
                            connected_nodes.extend(self.find_connected_nodes(edge_type, node))
                    else:
                        node = graph_fragment[edge]
                        connected_nodes.append((node['id'], edge_type))
                        connected_nodes.extend(self.find_connected_nodes(edge_type, node))
        return connected_nodes

    def _get_definition(self, definition_name):
        if definition_name not in self._definitions:
            # This will raise a KeyError if not found
            self._definitions[definition_name] = Definition(definition_importers[
                                                                definition_name].find_module(
                definition_name).load_module(definition_name).definition)
        return self._definitions[definition_name]

    def _get_app_token(self):
        assert self.app_id and self.app_secret
        url = "{}/oauth/access_token" \
              "?client_id={}&client_secret={}&grant_type=client_credentials".format(GRAPH_URL,
                                                                                    self.app_id,
                                                                                    self.app_secret)
        resp = requests.get(url)
        self.token = resp.json()['access_token']

    def _perform_http_get(self, *args, paging=False, **kwargs):
        # Get an access token if necessary
        if not self.token:
            self._get_app_token()

        params = kwargs.pop('params', {})
        params['access_token'] = self.token

        node_graph = requests.get(params=params, *args, **kwargs).json()

        if paging:
            # Queue of pages to retrieve.
            paging_queue = collections.deque(self.find_paging_links(node_graph))

            # Retrieve pages. Note that additional pages may be appended to queue.
            while paging_queue:
                page_link, graph_fragment = paging_queue.popleft()
                paging_queue.extend(self.get_page(page_link, graph_fragment))

        return node_graph

    def find_paging_links(self, graph_fragment):
        """
        Returns a list of (link, graph locations) found in a graph fragment.

        Paging fragments are removed from the graph fragment.

        A paging fragment looks like this:
        "paging": {
            "cursors": {
                "before": "MTAxNTg2NzEwNjQ2MTA3MjUZD",
                "after": "MTAxNTg2MDc4MjM1MDA3MjUZD"
            },
            "next": "https://graph.facebook.com/v2.8/488852220724/photos?access_token=EAACEdEose0cBAPXryeVeI3B37Rn5usrawwJWwZAY4kP5AxjL69n5uO031d5RY7g8UVZAKX40cdwSKzcwIXVxBMvUPdA4EdrYoQV5bArK9zekzBw6nWEM92urh9qVl8kkNBwbwxblFJX7jtEOlwG7EHrhoPEiZAJO44aSSdPDwZBLknZB3JGIPLadztpMam8lQRm6wGnQ0VQZDZD&pretty=0&fields=id%2Clink&limit=25&after=MTAxNTg2MDc4MjM1MDA3MjUZD"
        }

        """
        page_queue = []
        if isinstance(graph_fragment, dict):
            if 'paging' in graph_fragment:
                assert "data" in graph_fragment
                if 'next' in graph_fragment['paging']:
                    # Add link, list to append to to paging queue
                    page_queue.append((graph_fragment['paging']['next'], graph_fragment['data']))
                # Removing paging from graph
                del graph_fragment['paging']
            for key, value in graph_fragment.items():
                page_queue.extend(self.find_paging_links(value))
        elif isinstance(graph_fragment, list):
            for value in graph_fragment:
                page_queue.extend(self.find_paging_links(value))

        return page_queue


class Definition:
    def __init__(self, definition_map):
        self.definition_map = definition_map
        default_fields_set = set()
        fields_set = set()
        default_edges_set = set()
        edges_set = set()
        for name, field_definition in self.definition_map.items():
            if 'edge_type' in field_definition:
                if field_definition.get('default'):
                    default_edges_set.add(name)
                else:
                    edges_set.add(name)
            else:
                if field_definition.get('default'):
                    default_fields_set.add(name)
                else:
                    fields_set.add(name)
        self.default_fields = tuple(sorted(default_fields_set))
        self.fields = tuple(sorted(fields_set))
        self.default_edges = tuple(sorted(default_edges_set))
        self.edges = tuple(sorted(edges_set))

    def get_edge_type(self, edge_name):
        return self.definition_map[edge_name]['edge_type']

    def should_follow_edge(self, edge_name):
        return self.definition_map[edge_name].get('follow_edge', True)


if __name__ == '__main__':
    main()
