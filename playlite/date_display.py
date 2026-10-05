"""Consistent dates for game-view and metadata labels."""
from datetime import datetime

_MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def display_date(value, fallback=''):
    if not value:
        return fallback
    text = str(value)
    try:
        date = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        try:
            date = datetime.strptime(text, '%Y-%m-%d')
        except ValueError:
            return text
    return f'{date.day:02d}-{_MONTHS[date.month - 1]}-{date.year:04d}'
