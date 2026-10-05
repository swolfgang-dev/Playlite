"""Installation folder size calculation shared by the library and editor."""
import os
from pathlib import Path


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
