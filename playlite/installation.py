"""Installation folder size calculation shared by the library and editor."""
import os
import copy
import json
from pathlib import Path


def record_installation_size(data, games, directory, size):
    """Merge a scan into the latest library without restoring removed entries."""
    from .library_storage import library_lock
    from .storage import atomic_json
    with library_lock(data):
        path = Path(data) / 'library.json'
        latest = json.loads(path.read_text()) if path.exists() else copy.deepcopy(games)
        changed = False
        for game in latest:
            if game.get('InstallDirectory') == directory:
                game['InstallSize'] = size
                changed = True
        if changed:
            atomic_json(path, latest)
        return latest


def installation_size(directory):
    root = Path(directory)
    if not root.is_absolute() or not root.is_dir():
        raise ValueError('Choose an existing installation folder first.')
    total = 0
    def fail(error):
        raise error
    for folder, _, files in os.walk(root, followlinks=False, onerror=fail):
        for name in files:
            path = Path(folder) / name
            if not path.is_symlink():
                total += path.stat().st_size
    return total


def format_size(value):
    amount = float(value)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if amount < 1000 or unit == 'TB':
            return f'{amount:.2f} {unit}' if unit != 'B' else f'{int(amount)} B'
        amount /= 1000
