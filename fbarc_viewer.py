from flask import Flask, redirect, url_for, abort, Response, stream_with_context
import os
import json
from collections import OrderedDict
import itertools
import fileinput
import sys

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'secret')

nodes = {}
first_node_id = None

# Load only if FBARCH_FILE env variable is available.
fbarch_filepath = os.environ.get('FBARCH_FILE')
if fbarch_filepath:
    with open(fbarch_filepath) as f:
        for l in f:
            node = json.loads(l.rstrip('\n'))
            nodes[node['id']] = node
            if first_node_id is None:
                first_node_id = node['id']


@app.route('/')
def home():
    return redirect(url_for('node', node_id=first_node_id))


@app.route('/<node_id>')
def node(node_id):
    if node_id not in nodes:
        abort(404)
    return Response(stream_with_context(stream_template('node.html', node_id=node_id,
                                                        node_lines=render_obj(nodes[node_id]))))


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
            cleaned_obj['Item {}'.format(count+1)] = item
    return cleaned_obj


def render_obj(obj, counter=None):
    if counter is None:
        counter = itertools.count()

    obj = clean_obj(obj)
    for line in obj_renderers.get(type(obj), render_other)(obj, counter):
        yield line


def render_string(obj, _):
    if obj.startswith('http'):
        yield '<a href="{}">{}</a>'.format(obj, obj)
    else:
        yield obj


def render_other(obj, _):
    yield obj


def render_list(list_obj, counter):
    if len(list_obj) == 1:
        for line in render_obj(list_obj[0], counter):
            yield '<li>'
            yield line
            yield '</li>'
    else:
        yield '<ul>'
        for item in list_obj:
            yield '<li>'
            for line in render_obj(item, counter):
                yield line
            yield '</li>'
        yield '</ul>'


def render_dict(dict_obj, counter):
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
            yield '<a data-toggle="collapse" href="#{}" aria-expanded="false" aria-controls="{}">'.format(item_id, item_id)
        yield key
        if collapsible:
            yield '</a>'
        yield '</b>: '
        if isinstance(value, list):
            yield '<span class="badge badge-info">{}</span>'.format(len(value))
        if key == 'id' and value in nodes:
            yield '<a href="{}">{}</a>'.format(url_for('node', node_id=value), value)
        else:
            if collapsible:
                yield '<div class="collapse" id="{}">'.format(item_id)
            for line in render_obj(value, counter):
                yield line
            if collapsible:
                yield '</div>'
        yield '</li>'

    yield '</ul>'


obj_renderers = {
    OrderedDict: render_dict,
    dict: render_dict,
    list: render_list,
    str: render_string
}

if __name__ == '__main__':
    for line in fileinput.input():
        node = json.loads(line)
        if 'id' in node:
            nodes[node['id']] = node
            if first_node_id is None:
                first_node_id = node['id']
        else:
            print('Error line: {}'.format(line))
            sys.exit(1)

    app.run()