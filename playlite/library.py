"""Library querying shared by list and grid views."""
from datetime import datetime

SORT_FIELDS = [('Name', 'Name'), ('ReleaseDate', 'Release date'), ('Developers', 'Developer'),
               ('Publishers', 'Publisher'), ('Added', 'Date added'), ('LastActivity', 'Last played'),
               ('Playtime', 'Playtime'), ('UserScore', 'User score')]
FILTER_FIELDS = [('Genres', 'Genre'), ('Platforms', 'Platform'), ('Features', 'Feature'),
                 ('Developers', 'Developer'), ('Publishers', 'Publisher'),
                 ('Source', 'Source'), ('CompletionStatus', 'Completion status'), ('ReleaseDate', 'Release date')]


def values(game, field):
    value = game.get(field)
    if field == 'ReleaseDate' and isinstance(value, dict):
        value = value.get('ReleaseDate')
    if field == 'Platforms' and value is None:
        return ['PC (Windows)']
    return value if isinstance(value, list) else ([value] if value else [])


def sort_value(game, field):
    if field == 'Name':
        return (game.get('SortingName') or game['Name']).casefold()
    value = game.get(field)
    if field in ('ReleaseDate', 'Added', 'LastActivity'):
        if isinstance(value, dict):
            value = value.get('ReleaseDate')
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=None)
        except ValueError:
            try:
                return datetime.strptime(value, '%Y-%m-%d')
            except ValueError:
                return None
    if isinstance(value, list):
        value = ', '.join(value)
    return value.casefold() if isinstance(value, str) and value else value


def query_games(games, search='', filters=None, sort='Name', descending=False):
    filters = filters or {}
    visible = []
    for game in games:
        if search.strip().casefold() not in game['Name'].casefold():
            continue
        if any(selected and selected not in values(game, field)
               for field, selected in filters.items() if field in dict(FILTER_FIELDS)):
            continue
        installed = filters.get('Installed', '')
        if installed and bool(game.get('IsInstalled')) != (installed == 'Installed'):
            continue
        if filters.get('Favorite') and not game.get('Favorite'):
            continue
        if not filters.get('ShowHidden') and game.get('Hidden'):
            continue
        visible.append(game)
    with_value = [game for game in visible if sort_value(game, sort) is not None]
    without_value = [game for game in visible if sort_value(game, sort) is None]
    key = lambda game: (sort_value(game, sort), (game.get('SortingName') or game['Name']).casefold())
    return sorted(with_value, key=key, reverse=descending) + sorted(without_value, key=lambda game: game['Name'].casefold())
