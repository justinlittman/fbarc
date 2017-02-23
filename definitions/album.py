definition = {
    'fields': [
        'name',
        'photo_count',
        'created_time',
        'description',
        'updated_time',
        'video_count'
    ],
    'extended_fields': [
        'backdated_time',
        'backdated_time_granularity',
        'event',
        'link',
        'location',
        'modified_major',
        'place',
        'type'
    ],
    'connections': {
        'photos': 'photo',
        'cover_photo': 'photo'
    },
    'extended_connections': {
        'comments': 'comment',
        'from': 'user'
        # 'likes': '',
        # 'reactions': '',
        # 'comments': ''
    }
}