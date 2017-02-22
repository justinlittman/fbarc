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


def load_node_type_definition(node_type_definition_package):
    """
    Returns a map of node_types to importers loaded from a package.
    """
    node_type_definition_importers = {}
    for importer, modname, _ in pkgutil.iter_modules(node_type_definition_package.__path__):
        node_type_definition_importers[modname] = importer
    return node_type_definition_importers


# Map of node type names to importers
node_type_definition_importers = {}
# Load node_types
node_type_definition_importers.update(load_node_type_definition(definitions))
# Override with local_node_types
node_type_definition_importers.update(load_node_type_definition(local_definitions))


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
        print(fb.generate_url(args.node, args.node_type_definition, escape=args.escape))
    else:
        # Load keys
        app_id, app_secret = load_keys(args)
        fb = Fbarc(app_id=app_id, app_secret=app_secret)
        if args.command == 'metadata':
            print_graph(fb.get_metadata(args.node), pretty=args.pretty)
        else:
            node_type_definition_name = args.node_type_definition
            if node_type_definition_name == 'discover':
                node_type_definition_name = fb.discover_type(args.node)

            print_graphs(fb.get_nodes(args.node, node_type_definition_name, args.levels), pretty=args.pretty)


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
    node_type_definition_choices = ['discover']
    node_type_definition_choices.extend(node_type_definition_importers.keys())
    graph_parser.add_argument('node_type_definition', choices=node_type_definition_choices,
                              help='node type definition to use to retrieve the node. discover will discover node type '
                                   'from API.')
    graph_parser.add_argument('node', help='identify node to retrieve by providing node id, username, or Facebook URL')
    graph_parser.add_argument('--levels', type=int, default='1',
                              help='number of levels of nodes to retrieve (default=1)')
    graph_parser.add_argument('--pretty', action='store_true', help='pretty print output')

    metadata_parser = subparsers.add_parser('metadata', help='retrieve metadata for a node from the Graph API')
    metadata_parser.add_argument('node', help='identify node to retrieve by providing node id, username, or Facebook '
                                              'URL')
    metadata_parser.add_argument('--pretty', action='store_true', help='pretty print output')

    url_parser = subparsers.add_parser('url', help='generate the url to retrieve the node from the Graph API')
    url_parser.add_argument('node_type_definition', choices=list(node_type_definition_importers.keys()),
                            help='node type definition to use to retrieve the node.')
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
        self._node_type_definitions = {}

    def generate_url(self, node_id, node_type_definition_name, escape=False):
        """
        Returns the url for retrieving the specified node from the Graph API
        given the node type definition.
        """
        url, params = self._prepare_request(node_id, node_type_definition_name)
        if not escape:
            return '{}?{}'.format(url, '&'.join(['{}={}'.format(k, v) for k, v in params.items()]))
        else:
            return requests.Request('GET', url, params=params).prepare().url

    def get_nodes(self, root_node_id, root_node_type_definition_name, levels=1):
        """
        Iterator for getting nodes, starting with the root node and proceeding
        for the specified number of levels of connected nodes.
        """
        node_queue = collections.deque()
        node_queue.appendleft((root_node_id, root_node_type_definition_name, 1))
        retrieved_nodes = set()
        while node_queue:
            node_id, node_type_definition_name, level = node_queue.popleft()
            log.debug('Popped %s (%s) of the node queue (level %s). %s nodes left on the node queue.',
                      node_id, node_type_definition_name, level, len(node_queue))
            if node_id not in retrieved_nodes:
                node_graph = self.get_node(node_id, node_type_definition_name)
                if level < levels:
                    connected_nodes = self.find_connected_nodes(node_type_definition_name, node_graph, extended=True)
                    log.debug("%s connected nodes found in %s and added to node queue.", len(connected_nodes), node_id)
                    for node_id, node_type_definition_name in connected_nodes:
                        node_queue.append((node_id, node_type_definition_name, level+1))
                retrieved_nodes.add(node_id)
                yield node_graph
            else:
                log.debug("%s has already been retrieved, so skipping.", node_id)

    def get_node(self, node_id, node_type_definition_name):
        """
        Gets a node graph as specified by the node type definition.
        """
        log.info("Getting node %s (%s)", node_id, node_type_definition_name)
        url, params = self._prepare_request(node_id, node_type_definition_name)
        node_graph = self._perform_http_get(url, params=params)

        # Queue of pages to retrieve.
        paging_queue = collections.deque(self.find_paging_links(node_graph))

        # Retrieve pages. Note that additional pages may be appended to queue.
        while paging_queue:
            page_link, graph_fragment = paging_queue.popleft()
            paging_queue.extend(self.get_page(page_link, graph_fragment))

        return node_graph

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

    def _prepare_request(self, node_id, node_type_definition_name):
        """
        Prepare the request url and params.

        The access token is not included in the params.
        """
        params = {
            'metadata': 1,
            'fields': self._prepare_field_param(node_type_definition_name, extended=True)
        }
        return self._prepare_url(node_id), params

    @staticmethod
    def _prepare_url(node_id):
        """
        Prepare a request url.
        """
        return "{}/{}".format(GRAPH_URL, node_id)

    def _prepare_field_param(self, node_type_definition_name, extended=False):
        """
        Construct the fields parameter.
        """
        node_type_definition = self._get_node_type_definition(node_type_definition_name)
        fields = []
        if extended:
            fields.append('metadata{type}')
        fields.extend(node_type_definition.get('fields', []))
        if extended:
            fields.extend(node_type_definition.get('extended_fields', []))
        for connection, connection_definition in node_type_definition.get('connections', {}).items():
            fields.append('{}{{{}}}'.format(connection, self._prepare_field_param(connection_definition)))
        if extended:
            for connection, connection_definition in node_type_definition.get('extended_connections', {}).items():
                fields.append('{}{{{}}}'.format(connection, self._prepare_field_param(connection_definition)))
        if 'id' not in fields:
            fields.insert(0, 'id')
        return ','.join(fields)

    def find_connected_nodes(self, node_type_definition_name, graph_fragment, extended=False):
        """
        Returns a list of (node ids, node type definition names) found in a graph fragment.
        """
        connected_nodes = []
        node_type_definition = self._get_node_type_definition(node_type_definition_name)
        # Get the connections from the node type definition.
        connections = list(node_type_definition.get('connections', {}).items())
        if extended:
            connections.extend(list(node_type_definition.get('extended_connections', {}).items()))

        for connection, connected_node_type_definition_name in connections:
            if connection in graph_fragment:
                for node in graph_fragment[connection]['data']:
                    connected_nodes.append((node['id'], connected_node_type_definition_name))
                    connected_nodes.extend(self.find_connected_nodes(connected_node_type_definition_name, node))
        return connected_nodes

    def _get_node_type_definition(self, node_type_definition_name):
        if node_type_definition_name not in self._node_type_definitions:
            # This will raise a KeyError if not found
            self._node_type_definitions[node_type_definition_name] = node_type_definition_importers[
                node_type_definition_name].find_module(node_type_definition_name).load_module(node_type_definition_name)
        return self._node_type_definitions[node_type_definition_name].definition

    def _get_app_token(self):
        assert self.app_id and self.app_secret
        url = "{}/oauth/access_token" \
              "?client_id={}&client_secret={}&grant_type=client_credentials".format(GRAPH_URL,
                                                                                    self.app_id,
                                                                                    self.app_secret)
        resp = requests.get(url)
        (_, self.token) = resp.text.split('=')

    def _perform_http_get(self, *args, **kwargs):
        # Get an access token if necessary
        if not self.token:
            self._get_app_token()

        params = kwargs.pop('params', {})
        params['access_token'] = self.token

        return requests.get(params=params, *args, **kwargs).json()

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


if __name__ == '__main__':
    main()
