import unittest
from collections import namedtuple
try:
    from unittest.mock import patch, MagicMock  # Python 3
except ImportError:
    from mock import patch, MagicMock  # Python 2

from fbarc import Fbarc

Importer = namedtuple('Importer', ['definition'])


class TestFbarc(unittest.TestCase):
    def setUp(self):
        self.fbarc = Fbarc()

    def test_prepare_field_params(self):
        # Add some definitions so that don't try to load
        self.fbarc._node_type_definitions['node_type1'] = Importer(definition={
            'fields': [
                'node_type1_field1',
                'node_type1_field2',
            ],
            'extended_fields': [
                'node_type1_extended_field1'
            ],
            'connections': {
                'node_type1_connection1': 'node_type2'
            },
            'extended_connections': {
                'node_type1_extended_connection1': 'node_type3'
            }
        })

        self.fbarc._node_type_definitions['node_type2'] = Importer(definition={
            'fields': [
                'node_type2_field1',
                'node_type2_field2',
            ],
            'extended_fields': [
                'node_type2_extended_field1'
            ],
            'connections': {
                'node_type2_connection1': 'node_type3'
            },
            'extended_connections': {
                'node_type2_extended_connection1': 'no_node_type'
            }
        })

        self.fbarc._node_type_definitions['node_type3'] = Importer(definition={
            'fields': [
                'node_type3_field1',
            ]
        })

        self.assertEqual('id,metadata{type},node_type1_field1,node_type1_field2,node_type1_extended_field1,'
                         'node_type1_connection1{id,node_type2_field1,node_type2_field2,'
                         'node_type2_connection1{id,node_type3_field1}},'
                         'node_type1_extended_connection1{id,node_type3_field1}',
                         self.fbarc._prepare_field_param('node_type1', extended=True))
        self.assertEqual('id,node_type1_field1,node_type1_field2,node_type1_connection1{id,node_type2_field1,'
                         'node_type2_field2,node_type2_connection1{id,node_type3_field1}}',
                         self.fbarc._prepare_field_param('node_type1'))
        self.assertEqual('id,node_type2_field1,node_type2_field2,node_type2_connection1{id,node_type3_field1}',
                         self.fbarc._prepare_field_param('node_type2'))
        self.assertEqual('id,metadata{type},node_type3_field1',
                         self.fbarc._prepare_field_param('node_type3', extended=True))

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
                         self.fbarc.get_page('https://graph.facebook.com/v2.8/488852220724/photos?access_token=EAACEdEos'
                                             'e0cBABNVIW', graph_fragement))
        self.assertEqual(2, len(graph_fragement))
        self.assertEqual(graph_fragement[1], page_fragment['data'][0])

    def test_find_connected_nodes(self):
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

        connected_nodes = self.fbarc.find_connected_nodes('page', graph, extended=True)
        self.assertEqual(6, len(connected_nodes))
        self.assertTrue(('488852220724', 'album') in connected_nodes)
        self.assertTrue(('10158676054290725', 'photo') in connected_nodes)
        self.assertTrue(('1231054860315578', 'photo') in connected_nodes)