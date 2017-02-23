definition = {
    'fields': [
        'created_time',
        'message'
    ],
    'extended_fields': [
        'comment_count',
        'like_count',
        'message_tags',
        'object',

    ],
    'connections': {
    },
    'extended_connections': {
        'parent': 'comment',
        'from': 'user'
    }
}