from flask import Flask, redirect, url_for, abort, Response, stream_with_context, jsonify, render_template
import os
import json
from collections import OrderedDict, Counter
import itertools
import sys
import argparse
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import sessionmaker
from itertools import islice
from contextlib import contextmanager

Base = declarative_base()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'secret')

nodes = {}
first_nodes = {}
stats_counters = {}
total_stats_counter = Counter()
filepaths = {}
use_index = False
# Mapping of root nodes to db filepaths
dbs = {}

SLICE_SIZE = 15


# # Load only if FBARCH_FILE env variable is available.
# fbarch_filepath = os.environ.get('FBARC_FILE')
# if fbarch_filepath:
#     with open(fbarch_filepath) as f:
#         for l in f:
#             node = json.loads(l.rstrip('\n'))
#             nodes[node['id']] = node
#             if 'metadata' in node:
#                 stats_counters[node['metadata']['type']] += 1
#             if first_node_id is None:
#                 first_node_id = node['id']


@app.route('/')
def index():
    return render_template('root_nodes.html', first_nodes=first_nodes)


@app.route('/<root_node>')
def root_node(root_node):
    if root_node not in first_nodes:
        abort(404)
    return redirect(url_for('node', root_node=root_node, node_id=first_nodes[root_node]))


@app.route('/stats')
def total_stats():
    return render_template('stats.html', stats=total_stats_counter)


@app.route('/<root_node>/stats')
def stats(root_node):
    if root_node not in stats_counters:
        abort(404)
    return render_template('stats.html', stats=stats_counters[root_node])


@app.route('/<root_node>/<node_id>.json')
def json_node(root_node, node_id):
    node = get_node(root_node, node_id)
    if not node:
        abort(404)
    return jsonify(node)


@app.route('/<root_node>/<node_id>')
def node(root_node, node_id):
    node = get_node(root_node, node_id)
    if not node:
        abort(404)
    return Response(stream_with_context(stream_template('node.html', root_node=root_node, node_id=node_id,
                                                        node_lines=render_obj(node, root_node, node_id))))


@app.route('/<root_node>/<node_id>/<field>')
def node_field(root_node, node_id, field):
    node = get_node(root_node, node_id)
    if not node or field not in node:
        abort(404)
    return Response(stream_with_context(stream_template('node.html', root_node=root_node, node_id=node_id, field=field,
                                                        node_lines=render_obj(node[field], root_node, node_id))))

@app.route('/<root_node>/<node_id>/<field>.json')
def json_node_field(root_node, node_id, field):
    node = get_node(root_node, node_id)
    if not node or field not in node:
        abort(404)
    return jsonify(node[field])


def stream_template(template_name, **context):
    app.update_template_context(context)
    t = app.jinja_env.get_template(template_name)
    rv = t.stream(context)
    rv.enable_buffering(5)
    return rv


def clean_obj(obj):
    cleaned_obj = obj
    # If a dict w/ a single data item, convert to a list
    if isinstance(obj, (dict, OrderedDict)) and len(obj) == 1 and 'data' in obj:
        cleaned_obj = obj['data']

    # If obj is a list of dicts convert to a dict
    if isinstance(obj, list) and len(obj) and isinstance(obj[0], dict):
        cleaned_obj = OrderedDict()
        for count, item in enumerate(obj):
            cleaned_obj['Item {}'.format(count + 1)] = item
    return cleaned_obj


def render_obj(obj, root_node, node_id, counter=None):
    if counter is None:
        counter = itertools.count()

    obj = clean_obj(obj)
    for line in obj_renderers.get(type(obj), render_other)(obj, counter, root_node, node_id):
        yield line


def render_string(obj, _, __, ___):
    if obj.startswith('http'):
        yield '<a href="{}">{}</a>'.format(obj, obj)
    else:
        yield obj


def render_other(obj, _, __, ___):
    yield obj


def render_list(list_obj, counter, root_node, node_id):
    if len(list_obj) == 1:
        for line in render_obj(list_obj[0], root_node, node_id, counter):
            yield '<li>'
            yield line
            yield '</li>'
    else:
        yield '<ul>'
        for item in list_obj:
            yield '<li>'
            for line in render_obj(item, root_node, node_id, counter):
                yield line
            yield '</li>'
        yield '</ul>'


def render_dict(dict_obj, counter, root_node, node_id):
    yield '<ul>'
    keys = list(dict_obj.keys())
    if not isinstance(dict_obj, OrderedDict):
        keys.sort()
    for key in keys:
        value = clean_obj(dict_obj[key])
        collapsible = isinstance(value, (list, OrderedDict)) and len(value) > 1
        yield '<li><b>'

        if collapsible:
            item_id = 'item_{}'.format(next(counter))
            yield '<a data-toggle="collapse" data-target="#{}" aria-expanded="false" aria-controls="{}"><u>'.format(
                item_id, item_id)
        yield key
        if collapsible:
            yield '</u></a>'
        yield '</b>: '
        if isinstance(value, list):
            yield '<span class="badge badge-info">{}</span>'.format(len(value))
        if key == 'id' and has_node(root_node, value):
            yield '<a href="{}">{}</a>'.format(url_for('node', root_node=root_node, node_id=node_id), value)
        else:
            if collapsible:
                yield '<div class="collapse" id="{}">'.format(item_id)
            sliced_value, is_sliced = slice(value)
            for line in render_obj(sliced_value, root_node, node_id, counter):
                yield line
            if is_sliced:
                yield '<a href="{}" class="ml-4">More ...</a>'.format(
                    url_for('node_field', root_node=root_node, node_id=node_id, field=key))
            if collapsible:
                yield '</div>'
        yield '</li>'

    yield '</ul>'


def slice(value):
    if isinstance(value, list) and len(value) > SLICE_SIZE:
        return value[:SLICE_SIZE], True
    elif isinstance(value, OrderedDict) and len(value) > SLICE_SIZE:
        return OrderedDict(islice(value.iteritems(), SLICE_SIZE)), True
    return value, False


obj_renderers = {
    OrderedDict: render_dict,
    dict: render_dict,
    list: render_list,
    str: render_string
}


def get_node(root_node, node_id):
    pos = None
    if not use_index:
        pos = nodes.get(root_node, {}).get(node_id)
    else:
        with session_scope(create_session_factory(dbs[root_node])) as session:
            node = session.query(Node).filter_by(node_id=node_id).first()
            if node:
                pos = node.offset
    if pos is not None:
        with open(filepaths[root_node], encoding='utf-8') as file:
            file.seek(pos)
            return json.loads(file.readline())
    return None


def has_node(root_node, node_id):
    if not use_index:
        return node_id in nodes.get(root_node, {})
    else:
        with session_scope(create_session_factory(dbs[root_node])) as session:
            return session.query(Node).filter_by(node_id=node_id).first() is not None


def get_db_filepath(json_filepath):
    root, _ = os.path.splitext(json_filepath)
    return '{}.db'.format(root)


def get_root_node(filepath):
    return os.path.splitext(os.path.basename(filepath))[0]


def load_json(filepath):
    stats_counter = Counter()
    nodes = {}
    first_node = None
    with open(filepath) as file:
        pos = 0
        line = file.readline()
        while line:
            node = json.loads(line.rstrip('\n'))
            if 'id' in node:
                nodes[node['id']] = pos
                if 'metadata' in node:
                    stats_counter[node['metadata']['type']] += 1
                if first_node is None:
                    first_node = node['id']
            else:
                print('Error line: {}'.format(line))
                sys.exit(1)
            pos = file.tell()
            line = file.readline()
    return first_node, nodes, stats_counter


@app.template_filter('nf')
def number_format_filter(num):
    """
    A filter for formatting numbers with commas.
    """
    return '{:,}'.format(num) if num is not None else ''


# Index persistence
def create_session_factory(db_filepath):
    engine = create_engine('sqlite:///{}'.format(db_filepath), echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@contextmanager
def session_scope(Session):
    """Provide a transactional scope around a series of operations."""
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()


class Node(Base):
    __tablename__ = 'nodes'

    node_id = Column(String, nullable=False)
    offset = Column(Integer, primary_key=True)

    def __repr__(self):
        return 'Node<node_id={}, offset={}>'.format(self.node_id, self.offset)


class Stat(Base):
    __tablename__ = 'stats'

    node_type = Column(String, primary_key=True)
    count = Column(Integer, nullable=False)

    def __repr__(self):
        return 'Stat<node_type={}, count={}>'.format(self.node_type, self.count)


def init(files, index=False):
    global use_index, nodes, first_nodes, stats_counters, total_stats_counter, filepaths, dbs

    load_filepaths = []
    for file_or_dirpath in files:
        if os.path.isfile(file_or_dirpath):
            load_filepaths.append(file_or_dirpath)
        else:
            for dirpath, _, filenames in os.walk(file_or_dirpath):
                for filename in filenames:
                    if filename.lower().endswith('.json') or filename.lower().endswith('.jsonl'):
                        load_filepaths.append(os.path.join(dirpath, filename))

    for filepath in load_filepaths:
        root_node = get_root_node(filepath)
        filepaths[root_node] = filepath
        if not index:
            print('Loading {}'.format(filepath))
            load_first_node, load_nodes, load_stats_counter = load_json(filepath)
            first_nodes[root_node] = load_first_node
            stats_counters[root_node] = load_stats_counter
            total_stats_counter.update(load_stats_counter)
            nodes[root_node] = load_nodes

        else:
            use_index = True
            db_filepath = get_db_filepath(filepath)
            dbs[root_node] = db_filepath

            if not os.path.exists(db_filepath):
                print('Indexing {}'.format(filepath))
                load_first_node, load_nodes, load_stats_counter = load_json(filepath)

                first_nodes[root_node] = load_first_node
                stats_counters[root_node] = load_stats_counter
                total_stats_counter.update(load_stats_counter)
                with session_scope(create_session_factory(db_filepath)) as session:
                    for node, offset in load_nodes.items():
                        session.add(Node(node_id=node, offset=offset))
                    for node_type, count in load_stats_counter.items():
                        session.add(Stat(node_type=node_type, count=count))
            else:
                print('Reading index {}'.format(filepath))
                with session_scope(create_session_factory(db_filepath)) as session:
                    # Get first node
                    first_node = session.query(Node).filter_by(offset=0).first()
                    first_nodes[root_node] = first_node.node_id

                    # Get stats
                    load_stats_counter = Counter()
                    for stat in session.query(Stat).all():
                        load_stats_counter[stat.node_type] = stat.count
                        total_stats_counter[stat.node_type] += stat.count
                    stats_counters[root_node] = load_stats_counter


if 'FBARC_FILES' in os.environ:
    init(os.environ.get('FBARC_FILES').split(','), os.environ.get('FBARC_INDEX', 'false').lower() == 'true')


if __name__ == '__main__':
    parser = argparse.ArgumentParser("fbarc_viewer")
    parser.add_argument('--index', action='store_true', help='use/create indexes for files')
    parser.add_argument('files', metavar='FILE', nargs='+', help='files or directories to read')

    args = parser.parse_args()

    init(args.files, args.index)

    app.run()
