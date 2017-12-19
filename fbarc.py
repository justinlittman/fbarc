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
import copy
from datetime import datetime, timedelta, timezone
import iso8601
import time

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

GRAPH_URL = "https://graph.facebook.com/v2.11"
DEFAULT_EDGE_SIZE = 100
DEFAULT_NODE_BATCH_SIZE = 20
PAGE_BATCH_SIZE = 50

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
    config = {}
    input_app_id = None
    input_app_secret = None
    input_short_access_token = None
    if args.config:
        config = load_config(args)
        if not config:
            input_app_id, input_app_secret, input_short_access_token = input_keys(args)
            if not input_short_access_token:
                save_config(args, input_app_id, input_app_secret)

    app_id = args.app_id or os.environ.get('APP_ID') or config.get('app_id') or input_app_id
    app_secret = args.app_secret or os.environ.get('APP_SECRET') or config.get('app_secret') or input_app_secret
    short_access_token = args.access_token or os.environ.get('ACCESS_TOKEN') or input_short_access_token
    long_access_token = config.get('access_token')
    expires_at = None
    if 'expires_at' in config:
        expires_at = iso8601.parse_date(config['expires_at'])

    if not (app_id and app_secret):
        sys.exit('App id and secret are required.')
    return app_id, app_secret, short_access_token, long_access_token, expires_at


def load_config(args):
    path = args.config
    profile = args.profile
    if not os.path.isfile(path):
        return {}

    config = configparser.ConfigParser(allow_no_value=True)
    config.read(path)
    data = {}
    try:
        for key, value in config.items(profile):
            data[key] = value
    except configparser.NoSectionError:
        sys.exit("no such profile %s in %s" % (profile, path))
    return data


def save_config(args, app_id, app_secret, access_token=None, expires_at=None):
    if not args.config:
        return
    config = configparser.ConfigParser()
    config.add_section(args.profile)
    config.set(args.profile, 'app_id', app_id)
    config.set(args.profile, 'app_secret', app_secret)
    if access_token and expires_at:
        config.set(args.profile, 'access_token', access_token)
        config.set(args.profile, 'expires_at', expires_at.isoformat())

    with open(args.config, 'w') as config_file:
        config.write(config_file)


def input_keys(args):
    print("Please enter Facebook API credentials")

    config = load_config(args)

    def i(name, optional=False):
        prompt = name.replace('_', ' ')
        if name in config:
            prompt += ' [%s]' % config[name]
        if optional:
            prompt += ' (optional)'
        return get_input(prompt + ": ") or config.get(name)

    app_id = i('app_id')
    app_secret = i('app_secret')
    short_access_token = i('short_access_token', optional=True)
    return app_id, app_secret, short_access_token


def main():
    parser = get_argparser()
    args = parser.parse_args()

    logging.basicConfig(
        filename=args.log,
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    if args.command is None:
        parser.print_help()
        sys.exit(1)
    elif args.command == 'configure':
        app_id, app_secret, short_access_token = input_keys(args)
        long_access_token = None
        expires_at = None
        if short_access_token:
            long_access_token, expires_at = prepare_long_access_token(app_id, app_secret, short_access_token)
        save_config(args, app_id, app_secret, long_access_token, expires_at)
    elif args.command == 'url':
        fb = Fbarc()
        print(fb.generate_url(args.node, args.definition, escape=args.escape))
    else:
        # Load keys
        app_id, app_secret, short_access_token, long_access_token, expires_at = load_keys(args)
        if short_access_token:
            long_access_token, expires_at = prepare_long_access_token(app_id, app_secret, short_access_token)
            save_config(args, app_id, app_secret, long_access_token, expires_at)
        token = long_access_token
        if token:
            print('Access token expires on {}'.format(expires_at), file=sys.stderr)
            if expires_at < datetime.now(timezone.utc):
                print('Warning: App token is expired.', file=sys.stderr)
            elif expires_at < datetime.now(timezone.utc) - timedelta(days=1):
                print('Warning: App token expires in less than a day.', file=sys.stderr)
        else:
            token = get_app_token(app_id, app_secret)
            print('Warning: Using an app token. You may encounter authorization problems.', file=sys.stderr)
        try:
            fb = Fbarc(token=token, delay_secs=args.delay)
            if args.command == 'metadata':
                if args.update:
                    node_type, fields, connections = fb.get_parsed_metadata(args.node)
                    fields.extend(connections)
                    definition = fb.get_definition(node_type)
                    print_definition_map(update_definition_map(definition.definition_map, fields),
                                         definition.node_batch_size, definition.edge_size)
                elif args.template:
                    _, fields, connections = fb.get_parsed_metadata(args.node)
                    fields.extend(connections)
                    print_definition_map(definition_map_template(fields), None, None)
                else:
                    print_graph(fb.get_metadata(args.node), pretty=args.pretty)
            elif args.command == 'search':
                print_graph(fb.search(args.node_type, args.query))
            else:
                definition_name = args.definition
                if definition_name == 'discover':
                    definition_name = fb.discover_type(args.node)

                print_graphs(fb.get_nodes(args.node, definition_name, levels=args.levels,
                                          exclude_definition_names=args.exclude), pretty=args.pretty)
        except FbException as e:
            print('Error: {}'.format(e.message), file=sys.stderr)
            if e.code == 100:
                print('Hint: Use a user token instead of an app token. See README for explanation.', file=sys.stderr)
            quit(1)


def update_definition_map(definition_map, field_names):
    new_definition_map = copy.deepcopy(definition_map)
    for field_name in field_names:
        if field_name not in new_definition_map:
            new_definition_map[field_name] = {'omit': True, 'comment': 'Added field'}
    return new_definition_map


def definition_map_template(field_names):
    definition_map = {}
    for name in field_names:
        definition_map[name] = {'omit': True}
    return definition_map


def print_graph(graph, pretty=False):
    print(json.dumps(graph, indent=4 if pretty else None))


def print_graphs(graph_iter, pretty=False):
    for graph in graph_iter:
        print_graph(graph, pretty)


def print_definition_map(definition_map, node_batch_size, edge_size):
    print('definition = {')
    if node_batch_size and node_batch_size != DEFAULT_NODE_BATCH_SIZE:
        print('    \'node_batch_size\': {},'.format(node_batch_size))
    if edge_size and edge_size != DEFAULT_EDGE_SIZE:
        print('    \'node_batch_size\': {},'.format(node_batch_size))
    definition_map.pop('id', None)
    print('    \'fields\': {')
    for name in sorted(definition_map.keys()):
        field_definition = definition_map[name]
        if 'comment' in field_definition:
            comment = field_definition.pop('comment')
            print('        # {}'.format(comment))
        print('        \'{}\': {},'.format(name, field_definition))
    print('    }')
    print('}')


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
    parser.add_argument("--access_token",
                        default=None, help="Facebook access token")
    parser.add_argument('--config', default=config,
                        help="Config file containing Facebook keys")
    parser.add_argument('--profile', default='main',
                        help="Name of a profile in your configuration file")
    parser.add_argument('--delay', type=float, help='delay between requests. (default=.5)', default=.5)

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
                              help='number of levels of nodes to retrieve (default=1, infinite=0)')
    graph_parser.add_argument('--exclude', nargs='+', choices=list(definition_importers.keys()),
                              help='node type definitions to exclude from recursive retrieval', default=[])
    graph_parser.add_argument('--pretty', action='store_true', help='pretty print output')

    metadata_parser = subparsers.add_parser('metadata', help='retrieve metadata for a node from the Graph API')
    metadata_parser.add_argument('node', help='identify node to retrieve by providing node id, username, or Facebook '
                                              'URL')
    metadata_parser.add_argument('--pretty', action='store_true', help='pretty print output')
    metadata_parser.add_argument('--template', action='store_true', help='output a definition template')
    metadata_parser.add_argument('--update', action='store_true',
                                 help='update existing template with additional fields')

    url_parser = subparsers.add_parser('url', help='generate the url to retrieve the node from the Graph API')
    url_parser.add_argument('definition', choices=list(definition_importers.keys()),
                            help='definition to use to retrieve the node.')
    url_parser.add_argument('node', help='identify node to retrieve by providing node id or username')
    url_parser.add_argument('--escape', action='store_true', help='escape the characters in the url')

    subparsers.add_parser('configure', help='input API credentials and store in configuration file')

    return parser


def prepare_long_access_token(app_id, app_secret, short_access_token):
    app_token = get_app_token(app_id, app_secret)
    # Create new long access token
    long_access_token = get_long_access_token(app_id, app_secret, short_access_token)
    expires_at = get_token_expires_at(app_token, long_access_token)

    return long_access_token, expires_at


def get_app_token(app_id, app_secret):
    url = "{}/oauth/access_token" \
          "?client_id={}&client_secret={}&grant_type=client_credentials".format(GRAPH_URL,
                                                                                app_id,
                                                                                app_secret)
    resp = requests.get(url)
    return resp.json()['access_token']


def get_long_access_token(app_id, app_secret, short_access_token):
    url = "{}/oauth/access_token?grant_type=fb_exchange_token" \
          "&client_id={}&client_secret={}&fb_exchange_token={}".format(GRAPH_URL,
                                                                       app_id,
                                                                       app_secret,
                                                                       short_access_token)
    response = requests.get(url)
    raise_for_fb_exception(response)
    return response.json()['access_token']


def get_token_expires_at(app_token, token):
    url = "{}/debug_token?input_token={}&access_token={}".format(GRAPH_URL,
                                                                 token,
                                                                 app_token)
    response = requests.get(url)
    raise_for_fb_exception(response)
    return datetime.fromtimestamp(response.json()['data']['expires_at'], timezone.utc)


def raise_for_fb_exception(response):
    if response.status_code != requests.codes.ok:
        try:
            error_response = response.json()
            log.error(json.dumps(error_response, indent=4))
            raise FbException(error_response)
        except json.decoder.JSONDecodeError:
            response.raise_for_status()
    response.raise_for_status()


class Fbarc(object):
    def __init__(self, token=None, delay_secs=.5):
        log.debug('Token is %s', token)
        self.token = token

        # Map of node types definition names to node type definitions
        self._definitions = {}

        self.last_get = None
        log.debug('Delay is %s', delay_secs)
        self.delay_secs = delay_secs
        self.get_errors_limit = 10
        self.get_error_delay_secs = 30

    def generate_url(self, node_id, definition_name, escape=False):
        """
        Returns the url for retrieving the specified node from the Graph API
        given the node type definition.
        """
        url, params = self._prepare_node_request(node_id, definition_name)
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
        node_counter = collections.Counter()
        node_queue = collections.deque()
        node_queue.appendleft((root_node_id, root_definition_name, 1))
        node_counter[root_definition_name] += 1
        retrieved_nodes = set()
        for node_ids, definition_name, level in self.node_queue_iter(node_queue):
            node_counter[definition_name] -= len(node_ids)
            log.debug('Popped %s %s nodes off node queue (level %s). %s nodes left on the node queue.',
                      len(node_ids), definition_name, level, len(node_queue))
            if definition_name is None or definition_name not in exclude_definition_names:
                log.info("Getting nodes %s (%s). %s nodes left: %s", node_ids, definition_name, len(node_queue),
                         node_counter.most_common())
                try:
                    node_graph_dict = self.get_node_batch(node_ids, definition_name)
                    if levels == 0 or level < levels:
                        for node_id, node_graph in node_graph_dict.items():
                            connected_nodes = self.find_connected_nodes(definition_name, node_graph,
                                                                        default_only=False)
                            log.debug("%s connected nodes found in %s and added to node queue.", len(connected_nodes),
                                      node_id)
                            for connected_node_id, connected_definition_name in connected_nodes:
                                if connected_node_id not in retrieved_nodes:
                                    log.debug('%s found in %s', connected_node_id, node_id)
                                    node_queue.append((connected_node_id, connected_definition_name, level + 1))
                                    node_counter[connected_definition_name] += 1
                            retrieved_nodes.add(node_id)
                            yield node_graph
                except FbException as e:
                    # Sometimes get unexpected GraphMethodException: Unsupported get request.
                    if e.code == 100 and e.subcode == 33:
                        log.warn('Skipping %s due to unexpected GraphMethodException: %s', node_id, e)
                    else:
                        raise e
            else:
                log.debug('%s is an excluded node type definition (%s), so skipping.',
                          node_id, definition_name)

    @staticmethod
    def node_queue_iter(node_queue):
        """
        Returns the next list of nodes, node definition, level where the node definition
        and level is the same for all nodes.

        The maximum number of nodes that will be returned is 50.
        """
        node_ids = []
        while node_queue:
            pop_node_id, pop_definition_name, pop_level = node_queue.popleft()
            node_ids.append(pop_node_id)

            peak_definition_name = None
            peak_level = None
            if node_queue:
                _, peak_definition_name, peak_level = node_queue[0]
            if peak_definition_name != pop_definition_name or peak_level != pop_level or len(node_ids) == 50:
                yield node_ids, pop_definition_name, pop_level
                node_ids = []

    def get_node(self, node_id, definition_name):
        """
        Gets a node graph as specified by the node type definition.
        """
        url, params = self._prepare_node_request(node_id, definition_name)
        node_graph = self._perform_http_get(url, params=params)

        # Queue of pages to retrieve.
        paging_queue = collections.deque(self.find_paging_links(node_graph))

        # Retrieve pages. Note that additional pages may be appended to queue.
        while paging_queue:
            pages = []
            for _ in range(min(PAGE_BATCH_SIZE, len(paging_queue))):
                page_link, graph_fragment = paging_queue.popleft()
                pages.append((page_link, graph_fragment))
            paging_queue.extend(self.get_page_batch(pages))

        return node_graph

    def get_node_batch(self, node_ids, definition_name):
        """
        Gets a node graphs for a list of nodes as specified by the node type definition.
        """
        url, params = self._prepare_nodes_request(node_ids, definition_name)
        # Returns a map of ids to graphs
        nodes_graph_dict = self._perform_http_get(url, params=params)

        for node_id in node_ids:
            if node_id in nodes_graph_dict:
                # Queue of pages to retrieve.
                paging_queue = collections.deque(self.find_paging_links(nodes_graph_dict[node_id]))
            else:
                log.warn('Node %s is missing or not permitted, so skipping.', node_id)

        definition = self.get_definition(definition_name)

        # Retrieve pages. Note that additional pages may be appended to queue.
        while paging_queue:
            pages = []
            for _ in range(min(definition.node_batch_size, len(paging_queue))):
                page_link, graph_fragment = paging_queue.popleft()
                pages.append((page_link, graph_fragment))
            paging_queue.extend(self.get_page_batch(pages))

        return nodes_graph_dict

    def get_page_batch(self, pages):
        log.debug('Getting batch with %s pages', len(pages))
        batch_list = []
        for page_link, _ in pages:
            batch_list.append({'method': 'GET', 'relative_url': page_link[len(GRAPH_URL) + 1:]})
        data = {'batch': json.dumps(batch_list), 'include_headers': 'false'}
        batch_json = self._perform_http_post(GRAPH_URL, data=data)

        new_pages = []
        for count, (_, graph_fragment) in enumerate(pages):
            batch_item = batch_json[count]
            body = json.loads(batch_item['body'])
            if batch_item['code'] != 200:
                raise FbException(body)
            new_pages.extend(self.merge_page(body, graph_fragment))
        return new_pages

    def merge_page(self, page_fragment, graph_fragment):
        """
        Merge a page fragment into a graph fragment.

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

    def get_parsed_metadata(self, node_id):
        """
        Returns (type, fields, connections) for a node.
        """
        field_names = []
        metadata = self.get_metadata(node_id)
        for field in metadata['metadata']['fields']:
            field_names.append(field['name'])
        return metadata['metadata']['type'], field_names, metadata['metadata']['connections'].keys()

    def discover_type(self, node_id):
        """
        Look up the type of a node.
        """
        return self.get_metadata(node_id)['metadata']['type']

    def _prepare_node_request(self, node_id, definition_name):
        """
        Prepare the request url and params for a single node.

        The access token is not included in the params.
        """
        params = {
            'metadata': 1,
            'fields': self._prepare_field_param(definition_name, default_only=False)
        }
        return self._prepare_url(node_id), params

    def _prepare_nodes_request(self, node_ids, definition_name):
        """
        Prepare the request url and params for multiple nodes.

        The access token is not included in the params.
        """
        params = {
            'ids': ','.join(node_ids),
            'metadata': 1,
            'fields': self._prepare_field_param(definition_name, default_only=False)
        }
        return GRAPH_URL, params

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
        definition = self.get_definition(definition_name)
        fields = []
        if not default_only:
            fields.append('metadata{type}')
        fields.extend(definition.default_fields)
        if not default_only:
            fields.extend(definition.fields)
        for edge in definition.default_edges:
            fields.append(
                '{}.limit({}){{{}}}'.format(edge, definition.edge_size,
                                            self._prepare_field_param(definition.get_edge_type(edge))))
        if not default_only:
            for edge in definition.edges:
                fields.append(
                    '{}.limit({}){{{}}}'.format(edge, definition.edge_size,
                                                self._prepare_field_param(definition.get_edge_type(edge))))
        if 'id' not in fields:
            fields.insert(0, 'id')
        return ','.join(fields)

    def find_connected_nodes(self, definition_name, graph_fragment, default_only=True):
        """
        Returns a list of (node ids, definition names) found in a graph fragment.
        """
        connected_nodes = []
        definition = self.get_definition(definition_name)
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

    def get_definition(self, definition_name):
        if definition_name not in self._definitions:
            # This will raise a KeyError if not found
            self._definitions[definition_name] = Definition(definition_importers[
                                                                definition_name].find_module(
                definition_name).load_module(definition_name).definition)
        return self._definitions[definition_name]

    def _perform_http_get(self, *args, use_token=True, try_count=1, **kwargs):
        # Optional delay
        if self.last_get:
            wait_secs = self.delay_secs - (datetime.now() - self.last_get).total_seconds()
            if wait_secs > 0:
                log.debug('Sleeping %s', wait_secs)
                time.sleep(wait_secs)
        self.last_get = datetime.now()

        params = kwargs.pop('params', {})
        if use_token:
            params['access_token'] = self.token

        try:
            response = requests.get(params=params, *args, **kwargs)
            raise_for_fb_exception(response)
        except requests.exceptions.ConnectionError as e:
            # Handle (possibly) transient connection errors
            logging.error('caught connection error %s on %s try', e, try_count)
            if self.get_errors_limit == try_count:
                logging.error('received too many errors')
                raise e
            else:
                time.sleep(self.get_error_delay_secs * try_count)
                return self._perform_http_get(*args, use_token=use_token, try_count=try_count + 1, **kwargs)
        except requests.exceptions.HTTPError as e:
            # Handle (possibly) transient http errors
            logging.error('caught http error %s on %s try', e, try_count)
            if e.response.status_code in (503, 504):
                if self.get_errors_limit == try_count:
                    logging.error('received too many errors')
                    raise e
                else:
                    time.sleep(self.get_error_delay_secs * try_count)
                    return self._perform_http_get(*args, use_token=use_token, try_count=try_count + 1, **kwargs)
            else:
                raise e

        except FbException as e:
            # Handle transient facebook errors
            if e.is_transient:
                logging.error('caught facebook error %s on %s try', e, try_count)
                if self.get_errors_limit == try_count:
                    logging.error('received too many errors')
                    raise e
                else:
                    time.sleep(self.get_error_delay_secs * try_count)
                    return self._perform_http_get(*args, use_token=use_token, try_count=try_count + 1, **kwargs)
            else:
                raise e
        return response.json()

    def _perform_http_post(self, *args, use_token=True, try_count=1, **kwargs):
        # Optional delay
        if self.last_get:
            wait_secs = self.delay_secs - (datetime.now() - self.last_get).total_seconds()
            if wait_secs > 0:
                log.debug('Sleeping %s', wait_secs)
                time.sleep(wait_secs)
        self.last_get = datetime.now()

        data = kwargs.pop('data', {})
        if use_token:
            data['access_token'] = self.token

        try:
            response = requests.post(data=data, *args, **kwargs)
            raise_for_fb_exception(response)
        except requests.exceptions.ConnectionError as e:
            # Handle (possibly) transient connection errors
            logging.error('caught connection error %s on %s try', e, try_count)
            if self.get_errors_limit == try_count:
                logging.error('received too many errors')
                raise e
            else:
                time.sleep(self.get_error_delay_secs * try_count)
                return self._perform_http_post(*args, use_token=use_token, try_count=try_count + 1, **kwargs)
        except requests.exceptions.HTTPError as e:
            # Handle (possibly) transient http errors
            logging.error('caught http error %s on %s try', e, try_count)
            if e.response.status_code in (503, 504):
                if self.get_errors_limit == try_count:
                    logging.error('received too many errors')
                    raise e
                else:
                    time.sleep(self.get_error_delay_secs * try_count)
                    return self._perform_http_post(*args, use_token=use_token, try_count=try_count + 1, **kwargs)
            else:
                raise e

        except FbException as e:
            # Handle transient facebook errors
            if e.is_transient:
                logging.error('caught facebook error %s on %s try', e, try_count)
                if self.get_errors_limit == try_count:
                    logging.error('received too many errors')
                    raise e
                else:
                    time.sleep(self.get_error_delay_secs * try_count)
                    return self._perform_http_post(*args, use_token=use_token, try_count=try_count + 1, **kwargs)
            else:
                raise e
        return response.json()

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
    def __init__(self, definition_obj):
        self.definition_map = definition_obj['fields']
        self.node_batch_size = definition_obj.get('node_batch_size', DEFAULT_NODE_BATCH_SIZE)
        self.edge_size = definition_obj.get('edge_size', DEFAULT_EDGE_SIZE)
        default_fields_set = set()
        fields_set = set()
        default_edges_set = set()
        edges_set = set()
        for name, field_definition in self.definition_map.items():
            if not field_definition.get('omit'):
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


class FbException(Exception):
    def __init__(self, error_json):
        super(FbException, self).__init__(error_json['error'].get('message'))
        self.message = error_json['error'].get('message')
        self.type = error_json['error'].get('type')
        self.code = error_json['error'].get('code')
        self.subcode = error_json['error'].get('error_subcode')
        self.is_transient = error_json['error'].get('is_transient', False)


if __name__ == '__main__':
    main()
