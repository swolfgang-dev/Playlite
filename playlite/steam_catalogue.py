"""Public Steam catalogue lookup for the core executable association picker."""
import html
import json
import re
import urllib.parse
import urllib.request
from .lutris_add import normalize_steam_id


def search_games(query):
    query = query.strip()
    if not query:
        raise ValueError('Enter a Steam game name or app ID.')
    match = re.fullmatch(r'https?://store\.steampowered\.com/app/(\d+)(?:[/?#].*)?', query)
    if query.isascii() and query.isdigit() or match:
        identity = normalize_steam_id(match.group(1) if match else query)
        return [{'id': identity, 'name': 'Steam app '+identity}]
    parameters = urllib.parse.urlencode({'term': query, 'l': 'english', 'cc': 'CA'})
    request = urllib.request.Request('https://store.steampowered.com/api/storesearch/?'+parameters,
                                     headers={'User-Agent': 'Playlite', 'Accept-Language': 'en'})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            content = response.read(2*1024*1024+1)
        if len(content) > 2*1024*1024:
            raise ValueError('Steam returned a response that is too large.')
        data = json.loads(content)
    except (OSError, ValueError, UnicodeError) as error:
        raise ValueError('Could not search Steam: '+str(error)) from error
    if not isinstance(data, dict) or not isinstance(data.get('items'), list):
        raise ValueError('Steam returned an invalid search response.')
    games = []
    seen = set()
    for item in data['items']:
        if not isinstance(item, dict) or item.get('type', 'app') != 'app' or not isinstance(item.get('name'), str):
            continue
        try:
            identity = normalize_steam_id(item.get('id'))
        except ValueError:
            continue
        name = html.unescape(item['name']).strip()
        if name and identity not in seen:
            games.append({'id': identity, 'name': name})
            seen.add(identity)
    return games
