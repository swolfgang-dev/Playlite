"""Import a Playnite JSON export and copy artwork into Playlite's own storage."""
import argparse
import json
import os
import uuid
import sys
from pathlib import Path

from PyQt6.QtGui import QImageReader

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playlite.artwork import artwork_directory
from playlite.library_storage import library_lock
from playlite.storage import atomic_bytes, atomic_json


def import_snapshot(export, files, destination, features=None, *, replace=False):
    destination, files = Path(destination), Path(files).resolve()
    sources = json.loads(Path(export).read_text())
    if not isinstance(sources, list) or any(not isinstance(item, dict) for item in sources):
        raise ValueError('The snapshot must contain a list of games.')
    if (destination / 'artwork').is_symlink():
        raise ValueError('The artwork folder must not be a symlink.')
    identities = set()
    for source in sources:
        identity = source.get('Id')
        artwork_directory(destination, identity)
        if identity in identities:
            raise ValueError('The snapshot contains duplicate game IDs.')
        identities.add(identity)
        if not isinstance(source.get('Name'), str) or not source['Name'].strip():
            raise ValueError('Each imported game needs a name.')
    if features is not None and not isinstance(features, dict):
        raise ValueError('Feature overrides must be a game-ID mapping.')
    with library_lock(destination):
        target = destination / 'library.json'
        if target.exists() and not replace:
            raise ValueError('A library already exists; use --replace to explicitly replace it.')
        created, directories = [], set()
        try:
            return _import_snapshot(sources, files, destination, features, created, directories)
        except Exception:
            for path in created:
                path.unlink(missing_ok=True)
            for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            raise


def _import_snapshot(sources, files, destination, features, created, directories):
    games = []
    token = uuid.uuid4().hex
    for source in sources:
        game = {key: source.get(key) for key in (
            'Id', 'Name', 'Description', 'InstallDirectory', 'ReleaseDate',
            'Genres', 'Developers', 'Publishers', 'Links', 'IsInstalled', 'Features')}
        if features is not None:
            game['Features'] = features.get(source['Id'], game.get('Features') or [])
        folder = files / source['Id']
        candidates = []
        if folder.is_dir() and folder.resolve().is_relative_to(files):
            for path in folder.iterdir():
                if not path.is_file() or not path.resolve().is_relative_to(files):
                    continue
                size = QImageReader(str(path)).size()
                if size.isValid():
                    candidates.append((path, size.width(), size.height()))
        for key in ('Icon', 'CoverImage', 'BackgroundImage'):
            value = source.get(key) or ''
            if not isinstance(value, str):
                raise ValueError('Artwork paths must be text.')
            original = files / value.replace('\\', '/')
            image = original if original.is_file() and original.resolve().is_relative_to(files) else None
            if image is None:
                if key == 'CoverImage':
                    choices = [c for c in candidates if c[2] > c[1] * 1.2]
                elif key == 'BackgroundImage':
                    choices = [c for c in candidates if c[1] > c[2] * 1.3]
                else:
                    choices = [c for c in candidates if .8 < c[1] / c[2] < 1.2]
                if choices:
                    image = max(choices, key=lambda c: c[1] * c[2])[0]
            game[key] = None
            if image:
                target = artwork_directory(destination, source['Id']) / (key + '-' + token + image.suffix)
                for directory in (destination / 'artwork', target.parent):
                    if not directory.exists():
                        directory.mkdir()
                        directories.add(directory)
                atomic_bytes(target, image.read_bytes())
                created.append(target)
                game[key] = str(target.relative_to(destination))
        actions = source.get('Actions') or []
        game['LutrisId'] = next((a['Path'].split('://', 1)[1] for a in actions
                                 if a.get('IsPlayAction') and
                                 (a.get('Path') or '').startswith('wine-bridge-lutris://')), None)
        path = game.get('InstallDirectory') or ''
        if path.lower().startswith('z:\\'):
            game['InstallDirectory'] = '/' + path[3:].replace('\\', '/')
        games.append(game)
    atomic_json(destination / 'library.json', games)
    return games


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path)
    parser.add_argument('files', type=Path)
    parser.add_argument('--features', type=Path, help='Optional game-ID to feature-name JSON mapping.')
    parser.add_argument('--destination', type=Path, default=Path(
        os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'playlite')
    parser.add_argument('--replace', action='store_true', help='Explicitly replace an existing library.')
    args = parser.parse_args()
    features = json.loads(args.features.read_text()) if args.features else None
    games = import_snapshot(args.export, args.files, args.destination, features, replace=args.replace)
    print(f'Imported {len(games)} games into {args.destination}')
