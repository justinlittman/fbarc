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
        'from': 'user'
    },
    'extended_connections': {
        'parent': 'comment',
        'comments': 'comment'
    }
}