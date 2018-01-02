from flask_frozen import Freezer
from flask import Flask, abort, jsonify, render_template
from flask_frozen import relative_url_for
import os
import json
from collections import Counter
import argparse

# Monkey patch
import fbarc_viewer
fbarc_viewer.url_for = relative_url_for

app = Flask(__name__)

# nodes = {}
# stats_counter = Counter()
# first_node_id = None


@app.route('/')
def home():
    return node(None, fbarc_viewer.first_node_id)


@app.route('/stats.html')
def stats():
    return render_template('stats.html', stats=fbarc_viewer.stats_counter)


@app.route('/<path:node_path>/<node_id>.json')
def json_node(node_path, node_id):
    if node_id not in fbarc_viewer.nodes:
        abort(404)
    return jsonify(fbarc_viewer.nodes[node_id])


@app.route('/<path:node_path>/<node_id>.html')
def node(node_path, node_id):
    if node_id not in fbarc_viewer.nodes:
        abort(404)
    return render_template('node.html', node_id=node_id, node_lines=fbarc_viewer.render_obj(fbarc_viewer.nodes[node_id]))


# To avoid putting too many files in a single directory, creating a node path
# created by splitting the node id into segments of 4 characters.
@app.url_defaults
def add_node_path(endpoint, values):
    if app.url_map.is_endpoint_expecting(endpoint, 'node_path'):
        values['node_path'] = '/'.join([values['node_id'][i:i+4] for i in range(0, len(values['node_id']), 4)])


def read_fb_json(filepath):
    fbarc_viewer.nodes = {}
    fbarc_viewer.stats_counter = Counter()
    fbarc_viewer.first_node_id = None

    with open(filepath) as file:
        for line in file:
            node = json.loads(line.rstrip('\n'))
            if 'id' in node:
                fbarc_viewer.nodes[node['id']] = node
                if 'metadata' in node:
                    fbarc_viewer.stats_counter[node['metadata']['type']] += 1
                if fbarc_viewer.first_node_id is None:
                    fbarc_viewer.first_node_id = node['id']


def freeze(json_filepath, output_dir):
    read_fb_json(json_filepath)
    dir_name, _ = os.path.splitext(os.path.basename(json_filepath))
    output_path = os.path.join(output_dir, dir_name)
    app.config['FREEZER_RELATIVE_URLS'] = True
    app.config['FREEZER_DESTINATION'] = output_path
    print('Freezing {} to {}'.format(json_filepath, output_path))
    freezer = Freezer(app)
    freezer.freeze()


if __name__ == '__main__':
    parser = argparse.ArgumentParser("fbarc")
    parser.add_argument('output_dir', help='Where to write the static files.')
    parser.add_argument('facebook_json', nargs='+', help='File(s) containing the Facebook JSON created by f(b)arc.')

    args = parser.parse_args()
    for json_filepath in args.facebook_json:
        freeze(json_filepath, args.output_dir)