definition = {
    'edge_size': 25,
    'node_batch_size': 10,
    'fields': {
        'actions': {'omit': True},
        'admin_creator': {'omit': True},
        'allowed_advertising_objectives': {'omit': True},
        'application': {'omit': True},
        'attachments': {'omit': True},
        'backdated_time': {'omit': True},
        'call_to_action': {'omit': True},
        # Removed since causes error
        'caption': {'omit': True},
        'child_attachments': {'omit': True},
        'comments': {'edge_type': 'comment'},
        'comments_mirroring_domain': {'omit': True},
        'coordinates': {'omit': True},
        'created_time': {'default': True},
        # Removed since causes error
        'description': {'omit': True},
        'dynamic_posts': {'omit': True},
        'event': {'edge_type': 'event', 'follow_edge': False},
        'expanded_height': {'omit': True},
        'expanded_width': {'omit': True},
        'feed_targeting': {'omit': True},
        'from': {'default': True},
        # Removed since causes error
        'full_picture': {'omit': True},
        'height': {'omit': True},
        # Removed since causes error
        'icon': {'omit': True},
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
        'link': {'omit': True},
        'message': {'default': True},
        'message_tags': {},
        'multi_share_end_card': {'omit': True},
        'multi_share_optimized': {'omit': True},
        # Removed since causes error
        'name': {'omit': True},
        # Removed since causes error
        'object_id': {'omit': True},
        # Removed since causes error
        'parent_id': {'omit': True},
        'permalink_url': {'default': True},
        # Removed since causes error
        'picture': {'omit': True},
        'place': {},
        'privacy': {'omit': True},
        'promotion_status': {'omit': True},
        # Removed since causes error
        'properties': {'omit': True},
        'reactions': {},
        'scheduled_publish_time': {'omit': True},
        'seen': {'omit': True},
        'sharedposts': {'omit': True},
        # For some reason, shares are causing (#2) Service temporarily unavailable on some posts.
        'shares': {'omit': True},
        # Removed since causes error
        'source': {'omit': True},
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
        'type': {'omit': True},
        'updated_time': {'default': True},
        'via': {},
        'video_buying_eligibility': {'omit': True},
        'width': {'omit': True},
        'with_tags': {'omit': True},
    }
}
