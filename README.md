# F(b)arc

(The "b" is silent.)

A commandline tool and Python library for archiving data from [Facebook](https://www.facebook.com/) using the [Graph API](https://developers.facebook.com/docs/graph-api).

Facebook data is represented as a graph. The graph is composed of:

* nodes:  Things on Facebook, such as Pages, Albums, and Photos. Each node has an id (e.g., 1322855124437680)
and a type (e.g., Page).
* fields:  Attributes such as things, such as name and id.
* edges:  Connections between nodes, e.g., Page's Photos.

The graph is represented as a JSON object. For example:

    {
      "name": "The White House",
      "id": "1191441824276882",
      "about": "Welcome to the official White House Facebook page.
    
    Comments posted on and messages received through White House pages are subject to the Presidential Records Act and may be archived. Learn more at WhiteHouse.gov/privacy.",
      "albums": {
        "data": [
          {
            "created_time": "2017-01-20T19:33:16+0000",
            "name": "Timeline Photos",
            "id": "1199645353456529"
          }
        ]
      },
      "metadata": {
        "type": "page"
      }          
    }

F(b)arc supports retrieving parts of the graph for archiving. To do so, it allows you to specify what fields
and edges to retrieve for a particular node type. (What fields and connections to
retrieve is referred to as a definition and is described further below).

## Getting API keys
Before you f(b)arc you will need to register an app. To do this:

1. If you don't already have one, create a Facebook account.
2. Go to [https://developers.facebook.com/apps/](https://developers.facebook.com/apps/) and log in.
3. Click `Add a New App` and complete the form.
4. From the app's dashboard, note the app id and app secret.

See below for more information on tokens.

## Install

_Note: pip install coming once f(b)arc is more stable._

These are instructions for Python 3. Make appropriate adjustments for Python 2.

1. Download f(b)arc or clone it:

        git clone https://github.com/justinlittman/fbarc.git

2. Change to the directory:

        cd fbarc
        
3. Optional: Create a [virtualenv](https://virtualenv.pypa.io/en/stable/):

        virtualenv -p python3 ENV
        source ENV/bin/activate
        
4. Install requirements:

        pip install -r requirements/requirement3.txt
        
5. Get commandline usage:

        python fbarc.py -h

## Usage

### Configure
Once you've got your API keys you can tell f(b)arc what they are with the
`configure` command.

    python fbarc.py configure

This will store your credentials in a file called `.fbarc` in your home
directory so you don't have to keep providing them. If you would rather supply
them directly you can set them in the environment (`APP_ID`, `APP_SECRET`) or using 
commandline options (`--app_id`, `--app_secret`).

### Tokens
Using the API requires an [access token](https://developers.facebook.com/docs/facebook-login/access-tokens).
F(b)arc supports app access tokens and user access tokens.

F(b)arc can retrieve an app access token using the app id and app secret. However, there
are some nodes that cannot be retrieved with an app access token, thus a user access token
is recommended.

A user access token allows retrieving more nodes than an app access token (but as used
in f(b)arc is still limited to public data). There are two types of user access tokens:
short-lived and long-lived tokens. Short-lived access tokens are valid for
around an hour; long-lived access tokens for a few months. Long-lived user access tokens
are retrieved using a short-lived user access tokens and the app id and app secret.

When given a short-lived access token (e.g., with the `configure` command), f(b)arc will
retrieve and store a long-lived access token. You can get a short-lived access token from
[https://developers.facebook.com/tools/accesstoken/](https://developers.facebook.com/tools/accesstoken/).

F(b)arc will warn you when you're long-lived user access token is going to expire.

### Graph
The graph command will retrieve the graph for a node (or use the graphs command to retrieve the graphs for
multiple nodes provided in files or stdin). The node is identified by a node id (e.g., 1191441824276882),
name (e.g., WhiteHouse) or a Facebook url (e.g., https://www.facebook.com/WhiteHouse/).

The node graph is retrieved according to the specified definition. If the type of a node is not
known, provide a definition of `discover` and f(b)arc will look up the node's type and
try to match it to a definition.

f(b)arc finds additional nodes in the graph for a node. For example, for a Page it may find the
Album nodes. The `--levels` parameter will determine the number of levels of nodes that are retrieved,
with the default being 1 (i.e., the graph for just the node that was requested). Each additional node
graph is returned separately. Setting `--levels` to 0 will continue until all nodes reachable by edges
are exhausted. Be careful, because depending on the definitions, this could be, well, infinite. Use the
`--exclude` parameter to exclude definitions from recursive retrieval.

Note that f(b)arc may need to make multiple requests to retrieve the entire node graph so executing the
graph command may take some time.

    python fbarc.py graph page 1191441824276882 --levels 2 --pretty

### Metadata
The metadata command will retrieve all of the fields and connections for a node.

    python fbarc.py metadata 1191441824276882 --pretty
    
Note that you may not be able to actually retrieve all of those fields or connections with the
level of permissions of your API keys. The API will ignore any fields or connections that you
cannot access.

The `--template` and `--update` parameters help with creating definitions. These are described below.

### Url
The url command will return the url for retrieving the graph of a node according to the specified
definition.

    python fbarc.py url page 1191441824276882
    
## Definitions
Definitions specify what fields and connections will be returned for a node type, as well as the
size of node batches and edges.

Definitions are represented as simple python configuration files stored in the `definitions`
or `local_definitions` directories. Definitions in `definitions` are distributed with f(b)arc. 
You can add additional definitions in `local_definitions`. A definition in `local_definitions`
with the same filename as a definition in `definitions` will take precedence.

Here is an example definition for a Page:

    definition = {
        'node_batch_size': 10,
        'edge_size': 10,
        'fields': {
            'albums': {'edge_type': 'album'},
            'bio': {},
            likes': {'edge_type': 'page', 'follow_edge': False},
            'name': {'default': True},
            'workflows': {'omit': True},
        }
    }

`fields` is a map of names to fields or edges to be retrieved for the node.

A name with an `edge_type` is an edge. The value of `edge_type` is the name of another definition.

A field or edge in which `default` is `True` will always be retrieved. Otherwise, the field or
edge will only be retrieved when the node is the primary node being retrieved. In other words,
default fields or edges specify the summary for a node type; other fields or edges are part
of the detail for a node type.

A field or edge in which `omit` is `True` will be ignored. This is helpful for keeping track of fields
or edges that have been considered, but are not to be retrieved.

If an edge has `follow_edge` set to `False` then only the default fields or edges will be retrieved
for that edge. That edge will be omitted from recursive retrieval. For example, for a Page, the
likes edge is set to not follow edges because this would cause retrieval of all pages that liked
this page, which is not desired.

`node_batch_size` and `edge_size` are optional; if omitted sensible defaults will be used. Node batch
size determines how many nodes of that type will be requested at a time. A larger number reduces the
number of requests to the API, speeding up retrieval. Edge size determines, when retrieving an edge, 
how many nodes to retrieve. A larger number reduces the number of paging requests, speeding up retrieval.
In some cases, limits for node batch size and edge size can be found in the documentation; in others,
it must be found by trial and error.

The `--template` and `--update` parameters of the metadata command can assist with creating definitions.
`--template` will produce a definition for a node type that includes all possible fields or edges with 
`omit` set to `True` by default. `--update` will update an existing definition with any new fields or edges 
that are not already included in the definition. The new field or edges will be indicated by a comment 
("Added field") and will have `omit` set to `True`.

The [Graph API Explorer](https://developers.facebook.com/tools/explorer) is helpful for understanding
the fields and connections that are available for a node type. Less helpful is the 
[Graph API Reference](https://developers.facebook.com/docs/graph-api/reference).

## Graph API flakiness
Sometimes for inexplicable reasons, the Graph API will report errors for particular fields. For example,
as of late 2017, requesting the visitor_posts edge on [SenatorTedCruz](https://www.facebook.com/SenatorTedCruz)
with even a limit of 1 results in a "Please reduce the amount of data you're asking for, then retry your request"
error.

To handle this, f(b)arc support node overrides. Node overrides allow specifying fields to omit when requesting
particular nodes. When you encounter an error, the best way to determine which fields to omit is to experiment
with the Graph API Explorer.

To configure node overrides, create a node overrides JSON configuration file. (See `example.node_overrides.json`
for an example.) F(b)arc will use `node_overrides.json` by default if found, but a different file can be specified
with the `--override` flag.

## F(b)arc Viewer
F(b)arc Viewer allows you to view and explore the data retrieved from the API.

There are two approaches for invoking:

    python fbarc_viewer.py <filepath(s) of file containing JSON>

or:

    export FLASK_APP=fbarc_viewer.py
    flask run
    
A handy shortcut to load data directly from `fbarch.py` is:

    python fbarc.py graph page TestyMcTestpage | python fbarc_viewer.py

Once F(b)arc Viewer is running, it will be available at [http://localhost:5000/](http://localhost:5000/).

### Freezing F(b)arc Viewer
Freezing will write static files from F(b)arc Viewer. These can be deployed to a web server
so that F(b)arc Viewer does not need to be kept running.

To run:

    python fbarc_viewer_freeze.py <output dir> <filepaths to JSONL files from f(b)arc
    
For example:

    python fbarc_viewer_freeze.py /var/www/html TestMcTestpage.jsonl


## Unit tests

To run unit tests:

        python -m unittest discover

## Limitations

### Users
Facebook limits retrieving Users. F(b)arc does not support retrieving Users from the `graph` command,
but it does retrieve them when connected from other nodes. The fields that are available are
extremely limited.

### Incremental archiving
It would be ideal to be able to perform incremental archiving, i.e., only retrieve new or updated nodes.
For example, only retrieve new Photos in an Album. Unfortunately, the Graph API doesn't support this.
In particular, [ordering](https://developers.facebook.com/docs/graph-api/using-graph-api#ordering) does
not appear to work as documented and if it did work, it is unclear what field is used for ordering.

Suggestions on a strategy for incremental harvesting would be appreciated.

## Not yet implemented
* [Search](https://developers.facebook.com/docs/graph-api/using-graph-api#search)
* Setup.py
* Travis configuration

## Acknowledgemens
F(b)arc borrows liberally from [Twarc](https://github.com/docnow/twarc) in code and spirit.

## Facebook policies
Please be mindful of the [Facebook Platform Policy](https://developers.facebook.com/policy/).