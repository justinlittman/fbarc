import unittest
from collections import namedtuple

try:
    from unittest.mock import patch, MagicMock  # Python 3
except ImportError:
    from mock import patch, MagicMock  # Python 2

from fbarc import Fbarc, Definition
from collections import OrderedDict

Importer = namedtuple('Importer', ['definition'])


class TestFbarc(unittest.TestCase):
    def setUp(self):
        self.fbarc = Fbarc()

    def test_prepare_field_params(self):
        # Add some definitions so that don't try to load
        self.fbarc._definitions['node_type1'] = Definition({
            'node_type1_field1': {
                'default': True
            },
            'node_type1_field2': {
                'default': True
            },
            'node_type1_extended_field1': {},
            'node_type1_connection1': {
                'edge_type': 'node_type2',
                'default': True
            },
            'node_type1_extended_connection1': {
                'edge_type': 'node_type3',
            }
        })

        self.fbarc._definitions['node_type2'] = Definition({
            'node_type2_field1': {
                'default': True
            },
            'node_type2_field2': {
                'default': True
            },
            'node_type2_extended_field1': {},
            'node_type2_connection1': {
                'edge_type': 'node_type3',
                'default': True
            },
            'node_type2_extended_connection1': {
                'edge_type': 'no_node_type'
            }
        })

        self.fbarc._definitions['node_type3'] = Definition({
            'node_type3_field1': {
                'default': True
            }
        })

        self.assertEqual('id,metadata{type},node_type1_field1,node_type1_field2,node_type1_extended_field1,'
                         'node_type1_connection1{id,node_type2_field1,node_type2_field2,'
                         'node_type2_connection1{id,node_type3_field1}},'
                         'node_type1_extended_connection1{id,node_type3_field1}',
                         self.fbarc._prepare_field_param('node_type1', default_only=False))
        self.assertEqual('id,node_type1_field1,node_type1_field2,node_type1_connection1{id,node_type2_field1,'
                         'node_type2_field2,node_type2_connection1{id,node_type3_field1}}',
                         self.fbarc._prepare_field_param('node_type1'))
        self.assertEqual('id,node_type2_field1,node_type2_field2,node_type2_connection1{id,node_type3_field1}',
                         self.fbarc._prepare_field_param('node_type2'))
        self.assertEqual('id,metadata{type},node_type3_field1',
                         self.fbarc._prepare_field_param('node_type3', default_only=False))

    @patch("fbarc.requests", autospec=True)
    def test_get_page(self, mock_requests):
        graph_fragement = [
            {
                "id": "10158607823500724",
                "link": "https://www.facebook.com/DonaldTrump/photos/a.488852220724.393301.153080620723"
            },
        ]

        page_fragment = {
            "data": [
                {
                    "id": "10158607823500725",
                    "link": "https://www.facebook.com/DonaldTrump/photos/a.488852220724.393301.153080620724"
                },
            ],
            "paging": {
                "cursors": {
                    "before": "MTAxNTg2MDc4MjM1MDA3MjUZD",
                    "after": "MTAxNTg1NTQzNTcxMjA3MjUZD"
                },
                "next": "https://graph.facebook.com/v2.8/488852220724/photos?access_token=EAACEdEose0cBABNVIWZAPVEKXBR",
                "previous": "https://graph.facebook.com/v2.8/488852220724/photos?access_token=EAACEdEose0cBABNVIWZAPVE",
            }
        }

        mock_response = MagicMock()
        mock_requests.get.return_value = mock_response
        mock_response.json.return_value = page_fragment
        self.assertEqual([('https://graph.facebook.com/v2.8/488852220724/photos?access_token=EAACEdEose0cBABNVIWZAPVEKX'
                           'BR', graph_fragement)],
                         self.fbarc.get_page(
                             'https://graph.facebook.com/v2.8/488852220724/photos?access_token=EAACEdEos'
                             'e0cBABNVIW', graph_fragement))
        self.assertEqual(2, len(graph_fragement))
        self.assertEqual(graph_fragement[1], page_fragment['data'][0])

    def test_find_connected_nodes(self):
        self.fbarc._definitions['album'] = Definition({
            'cover_photo': {'edge_type': 'photo'},
            'photos': {'edge_type': 'photo', 'default': True}
        })
        self.fbarc._definitions['page'] = Definition({
            'albums': {'edge_type': 'album'},
        })
        graph = {
            "albums": {
                "data": [
                    {
                        "cover_photo": {
                            "created_time": "2017-02-22T14:46:01+0000",
                            "name": "Happy birthday, George Washington! Learn more about our first President here: http://45.wh.g",
                            "id": "1231054860315578"
                        },
                        "photos": {
                            "data": [
                                {
                                    "id": "10158680599675725",
                                    "link": "https://www.facebook.com/DonaldTrump/photos/a.488852220724.393301.15308062"
                                },
                                {
                                    "id": "10158676054290725",
                                    "link": "https://www.facebook.com/DonaldTrump/photos/a.488852220724.393301.15308062"
                                }
                            ]
                        },
                        "name": "Timeline Photos",
                        "id": "488852220724"
                    },
                    {
                        "photos": {
                            "data": [
                                {
                                    "id": "10158579670840725",
                                    "link": "https://www.facebook.com/DonaldTrump/photos/a.10158579704620725.1073741836"
                                }
                            ]
                        },
                        "name": "PRESIDENT TRUMP - - FIRST 100 DAYS",
                        "id": "10158579704620725"
                    }
                ]
            },
            "id": "153080620724"
        }

        default_connected_nodes = self.fbarc.find_connected_nodes('page', graph, default_only=True)
        self.assertEqual(0, len(default_connected_nodes))
        connected_nodes = self.fbarc.find_connected_nodes('page', graph, default_only=False)
        self.assertEqual(5, len(connected_nodes))
        self.assertTrue(('488852220724', 'album') in connected_nodes)
        self.assertTrue(('10158676054290725', 'photo') in connected_nodes)

    def test_follow_edge(self):
        graph = {
            "likes": {
                "data": [
                    {
                        "id": "10557079749",
                        "about": "Welcome to The Estelle and Melvin Gelman Library's Official Facebook Page.",
                        "category": "Library",
                        "name": "Gelman Library",
                        "link": "https://www.facebook.com/gelmanlibrary/",
                        "username": "gelmanlibrary",
                        "website": "library.gwu.edu"
                    }
                ]
            },
        }

        self.fbarc._definitions['page'] = Definition({
            'likes': {'edge_type': 'page'},
        })
        connected_nodes = self.fbarc.find_connected_nodes('page', graph, default_only=False)
        self.assertEqual(1, len(connected_nodes))
        self.assertTrue(('10557079749', 'page') in connected_nodes)

        self.fbarc._definitions['page'] = Definition({
            'likes': {'edge_type': 'page', 'follow_edge': False},
        })
        self.assertFalse(self.fbarc.find_connected_nodes('page', graph, default_only=False))
