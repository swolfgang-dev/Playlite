"""Recover references after standardizing artwork filenames."""
import copy
from pathlib import Path

NAMES = {'Icon': 'icon', 'CoverImage': 'cover-art', 'HeaderImage': 'header', 'BackgroundImage': 'background'}


def artwork_directory(data, identity):
    """Keep an entry's artwork within its own directory, including legacy IDs."""
    if (not isinstance(identity, str) or not identity or identity in ('.', '..')
            or any(character in identity for character in ('/', '\\', '\0'))):
        raise ValueError('Game ID must be a nonempty filename component.')
    root = Path(data) / 'artwork'
    directory = root / identity
    if directory.is_symlink() or directory.resolve().parent != root.resolve():
        raise ValueError('Game artwork directory is outside the artwork folder.')
    return directory


def repair_artwork(game, data):
    result = copy.deepcopy(game)
    directory = artwork_directory(data, result['Id'])
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
