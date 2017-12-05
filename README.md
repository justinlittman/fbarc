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

### Graph
The graph command will retrieve the graph for a node. The node is identified by a node id (e.g., 1191441824276882),
name (e.g., WhiteHouse) or a Facebook url (e.g., https://www.facebook.com/WhiteHouse/).

The node graph is retrieved according to the specified definition. If the type of a node is not
known, provide a definition of `discover` and f(b)arc will look up the node's type and
try to match it to a definition.

f(b)arc finds additional nodes in the graph for a node. For example, for a Page it may find the
Album nodes. The `--levels` parameter will determine the number of levels of nodes that are retrieved,
with the default being 1 (i.e., the graph for just the node that was requested). Each additional node
graph is returned separately. Use the `--exclude` parameter to exclude definitions from recursive
retrieval.

Note that f(b)arc may need to make multiple requests to retrieve the entire node graph so executing the
graph command may take some time.

    python fbarc.py graph page 1191441824276882 --levels 2 --pretty

### Metadata
The metadata command will retrieve all of the fields and connections for a node.

    python fbarc.py metadata 1191441824276882 --pretty
    
Note that you may not be able to actually retrieve all of those fields or connections with the
level of permissions of your API keys. The API will ignore any fields or connections that you
cannot access.

### Url
The url command will return the url for retrieving the graph of a node according to the specified
definition.

    python fbarc.py url page 1191441824276882
    
## Definitions
Definitions specify what fields and connections will be returned for a node type.

Definitions are represented as simple python configuration files stored in the `definitions`
or `local_definitions` directories. Definitions in `definitions` are distributed with f(b)arc. 
You can add additional definitions in `local_definitions`. A definition in `local_definitions`
with the same filename as a definition in `definitions` will take precedence.

Here is an example definition for a Page:

    definition = {
        'albums': {'edge_type': 'album'},
        'bio': {},
        likes': {'edge_type': 'page', 'follow_edge': False},
        'name': {'default': True}
    }

A definition is a specified as a map of names to fields or edges to be retrieved for the node.

A name with an `edge_type` is an edge. The value of `edge_type` is the name of another definition.

A field or edge in which `default` is `True` will always be retrieved. Otherwise, the field or
edge will only be retrieved when the node is the primary node being retrieved. In other words,
default fields or edges specify the summary for a node type; other fields or edges are part
of the detail for a node type.

If an edge has `follow_edge` set to `False` then only the default fields or edges will be retrieved
for that edge. That edge will be omitted from recursive retrieval. For example, for a Page, the
likes edge is set to not follow edges because this would cause retrieval of all pages that liked
this page, which is not desired.

The [Graph API Explorer](https://developers.facebook.com/tools/explorer) is helpful for understanding
the fields and connections that are available for a node type. Less helpful is the 
[Graph API Reference](https://developers.facebook.com/docs/graph-api/reference).

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
* [Handling exceptions](https://developers.facebook.com/docs/graph-api/using-graph-api#errors), including rate limits and key expiration.
* [Search](https://developers.facebook.com/docs/graph-api/using-graph-api#search)
* Setup.py
* Travis configuration

## Acknowledgemens
F(b)arc borrows liberally from [Twarc](https://github.com/docnow/twarc) in code and spirit.

## Facebook policies
Please be mindful of the [Facebook Platform Policy](https://developers.facebook.com/policy/).