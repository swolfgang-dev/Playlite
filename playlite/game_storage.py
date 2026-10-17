"""Persist games and their artwork independently of editor widgets."""
from datetime import datetime
from pathlib import Path
import shutil
import stat
from .artwork import repair_artwork
from .storage import atomic_bytes, atomic_json

def save_game(data, games, updated):
    from .artwork import artwork_directory
    artwork_directory(data, updated.get('Id'))
    from .library_storage import library_lock
    with library_lock(data):
        return _save_game(data, games, updated)


def _save_game(data, games, updated):
    """Commit integration settings with the library save, rolling back on failure."""
    from contextlib import ExitStack
    from .providers import discover_plugins, GameProvider, GenericPlugin
    with ExitStack() as pending:
        for provider in discover_plugins().values():
            save_settings = getattr(provider, 'save_action_settings', None)
            if isinstance(provider, (GameProvider, GenericPlugin)) and callable(save_settings):
                pending.enter_context(save_settings(updated))
        return _persist_game(data, games, updated)


def _persist_game(data, games, updated):
    """Copy new artwork and atomically persist an edited game without mutating the input."""
    import json
    result = repair_artwork(updated, data)
    # Other entries may have been migrated since this window loaded them.
    if (data / 'library.json').exists():
        games = json.loads((data / 'library.json').read_text())
    games = [repair_artwork(game, data) for game in games]
    backups = {}
    obsolete = set()
    names = {'Icon': 'icon', 'HeaderImage': 'header', 'CoverImage': 'cover-art', 'BackgroundImage': 'background'}
    directory = data / 'artwork' / result['Id']
    previous = next((game for game in games if game['Id'] == result['Id']), {})
    from .providers import discover_plugins, GenericPlugin
    for plugin in discover_plugins().values():
        if isinstance(plugin, GenericPlugin):
            plugin.prepare_edit_save(previous, result)
    if not result.get('Added'):
        if previous.get('Added'):
            result['Added'] = previous['Added']
        elif not previous:
            result['Added'] = datetime.now().astimezone().isoformat(timespec='seconds')
    try:
        for key, name in names.items():
            value = result.get(key)
            old = previous.get(key)
            if old:
                old_path = Path(old)
                if not old_path.is_absolute():
                    old_path = data / old_path
                if old_path.parent == directory:
                    obsolete.add(old_path)
            if not value:
                continue
            source = Path(value)
            if not source.is_absolute():
                source = data / source
            target = directory / f'{name}{source.suffix.lower()}'
            directory.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                raise ValueError('Saved artwork cannot be a symlink.')
            if source != target:
                original = (target.read_bytes(), stat.S_IMODE(target.stat().st_mode)) if target.exists() else None
                content = source.read_bytes()
                atomic_bytes(target, content, mode=stat.S_IMODE(source.stat().st_mode))
                backups[target] = (original, content)
                if source.parent == directory:
                    obsolete.add(source)
            result[key] = str(target.relative_to(data))
        retained = {data / result[key] for key in names if result.get(key)}
        if directory.exists():
            for path in directory.iterdir():
                if path.is_file() and (path.stem in names or any(path.stem.startswith(key + '-') for key in names) or path.stem in names.values()):
                    obsolete.add(path)
        replacement = [result if game['Id'] == result['Id'] else game for game in games]
        if not any(game['Id'] == result['Id'] for game in games):
            replacement.append(result)
        data.mkdir(parents=True, exist_ok=True)
        if (data / 'library.json').exists():
            shutil.copy2(data / 'library.json', data / 'library.json.bak')
        atomic_json(data / 'library.json', replacement)
        for path in obsolete - retained:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        return replacement
    except Exception:
        for path, (original, written) in backups.items():
            try:
                # A failed save must not overwrite a concurrent external edit.
                if path.is_symlink() or not path.exists() or path.read_bytes() != written:
                    continue
                if original is None:
                    path.unlink()
                else:
                    atomic_bytes(path, original[0], mode=original[1])
            except OSError:
                import logging
                logging.exception('Could not restore artwork after failed game save: %s', path)
        raise
