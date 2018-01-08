definition = {
    'edge_size': 25,
    'node_batch_size': 5,
    'fields': {
        'actions': {'omit': True},
        'admin_creator': {'omit': True},
        'allowed_advertising_objectives': {'omit': True},
        'application': {'omit': True},
        'attachments': {},
        'backdated_time': {'omit': True},
        'call_to_action': {'omit': True},
        # Removed since causes error
        'caption': {},
        'child_attachments': {'omit': True},
        'comments': {'edge_type': 'comment'},
        'comments_mirroring_domain': {'omit': True},
        'coordinates': {'omit': True},
        'created_time': {'default': True},
        # Removed since causes error
        'description': {},
        'dynamic_posts': {'omit': True},
        'event': {'edge_type': 'event', 'follow_edge': False},
        'expanded_height': {'omit': True},
        'expanded_width': {'omit': True},
        'feed_targeting': {'omit': True},
        'from': {'default': True},
        # Removed since causes error
        'full_picture': {},
        'height': {'omit': True},
        # Removed since causes error
        'icon': {},
        'insights': {'omit': True},
        'instagram_eligibility': {'omit': True},
        'is_app_share': {'omit': True},
        'is_expired': {'omit': True},
        'is_hidden': {'omit': True},
        'is_instagram_eligible': {'omit': True},
        'is_popular': {'omit': True},
        'is_published': {'omit': True},
        'is_spherical': {'omit': True},
        'likes': {},
        # Removed since causes error
        'link': {},
        'message': {'default': True},
        'message_tags': {},
        'multi_share_end_card': {'omit': True},
        'multi_share_optimized': {'omit': True},
        # Removed since causes error
        'name': {},
        # Removed since causes error
        'object_id': {},
        # Removed since causes error
        'parent_id': {},
        'permalink_url': {'default': True},
        # Removed since causes error
        'picture': {},
        'place': {},
        'privacy': {'omit': True},
        'promotion_status': {'omit': True},
        # Removed since causes error
        'properties': {},
        'reactions': {},
        'scheduled_publish_time': {'omit': True},
        'seen': {'omit': True},
        'sharedposts': {'omit': True},
        # Causes (#2) Service temporarily unavailable on some posts, e.g., 7935122852_217836351604866
        'shares': {'omit_on_error': 2},
        # Removed since causes error
        'source': {},
        'sponsor_tags': {'omit': True},
        'status_type': {'default': True},
        'story': {},
        'story_tags': {'omit': True},
        'subscribed': {'omit': True},
        'target': {'omit': True},
        'targeting': {'omit': True},
        'timeline_visibility': {'omit': True},
        'to': {'default': True},
        # Removed since causes error
        'type': {},
        'updated_time': {'default': True},
        'via': {},
        'video_buying_eligibility': {'omit': True},
        'width': {'omit': True},
        'with_tags': {'omit': True},
    }
}
