definition = {
    'node_batch_size': 5,
    'fields': {
        'album': {'edge_type': 'album', 'follow_edge': False},
        'backdated_time': {},
        'backdated_time_granularity': {},
        'can_backdate': {'omit': True},
        'can_delete': {'omit': True},
        'can_tag': {'omit': True},
        'comments': {'edge_type': 'comment'},
        'created_time': {'default': True},
        'event': {'edge_type': 'event', 'follow_edge': False},
        'from': {},
        'height': {},
        'icon': {},
        'images': {},
        'insights': {'omit': True},
        'likes': {},
        'link': {'default': True},
        'name': {'default': True},
        'name_tags': {'omit': True},
        'page_story_id': {},
        'picture': {},
        'place': {},
        'reactions': {},
        'sharedposts': {'omit': True},
        'sponsor_tags': {'omit': True},
        'tags': {},
        'target': {},
        'updated_time': {'default': True},
        'webp_images': {'omit': True},
        'width': {},
    }
}
