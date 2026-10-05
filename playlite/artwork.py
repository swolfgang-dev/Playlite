"""Recover references after standardizing artwork filenames."""
import copy
from pathlib import Path

NAMES = {'Icon': 'icon', 'CoverImage': 'cover-art', 'HeaderImage': 'header', 'BackgroundImage': 'background'}


def repair_artwork(game, data):
    result = copy.deepcopy(game)
    directory = data / 'artwork' / result['Id']
    if 'HeaderImage' not in result and result.get('BackgroundImage'):
        old = Path(result['BackgroundImage'])
        source = old if old.is_absolute() else data / old
        headers = list(directory.glob('header.*'))
        if not source.exists() and headers:
            result['HeaderImage'] = str(headers[0].relative_to(data))
            result['BackgroundImage'] = None
    for key, stem in NAMES.items():
        value = result.get(key)
        if not value:
            continue
        source = Path(value)
        source = source if source.is_absolute() else data / source
        if source.exists():
            continue
        candidates = sorted(path for path in directory.glob(stem + '*') if path.is_file() and path.stem == stem)
        if len(candidates) == 1:
            result[key] = str(candidates[0].relative_to(data))
    return result
