"""Import a Playnite JSON export and copy artwork into Playlite's own storage."""
import argparse
import json
import os
import shutil
from pathlib import Path

from PyQt6.QtGui import QImageReader


def import_snapshot(export, files, destination, features=None):
    destination.mkdir(parents=True, exist_ok=True)
    games = []
    for source in json.loads(export.read_text()):
        game = {key: source.get(key) for key in (
            'Id', 'Name', 'Description', 'InstallDirectory', 'ReleaseDate',
            'Genres', 'Developers', 'Publishers', 'Links', 'IsInstalled', 'Features')}
        if features is not None:
            game['Features'] = features.get(source['Id'], game.get('Features') or [])
        folder = files / source['Id']
        candidates = []
        if folder.exists():
            for path in folder.iterdir():
                size = QImageReader(str(path)).size()
                if size.isValid():
                    candidates.append((path, size.width(), size.height()))
        for key in ('Icon', 'CoverImage', 'BackgroundImage'):
            original = files / (source.get(key) or '').replace('\\', '/')
            image = original if original.is_file() else None
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
                target = destination / 'artwork' / source['Id'] / (key + image.suffix)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(image, target)
                game[key] = str(target.relative_to(destination))
        actions = source.get('Actions') or []
        game['LutrisId'] = next((a['Path'].split('://', 1)[1] for a in actions
                                 if a.get('IsPlayAction') and
                                 (a.get('Path') or '').startswith('wine-bridge-lutris://')), None)
        path = game.get('InstallDirectory') or ''
        if path.lower().startswith('z:\\'):
            game['InstallDirectory'] = '/' + path[3:].replace('\\', '/')
        games.append(game)
    target = destination / 'library.json'
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(games, indent=2, ensure_ascii=False))
    temporary.replace(target)
    return games


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path)
    parser.add_argument('files', type=Path)
    parser.add_argument('--features', type=Path, help='Optional game-ID to feature-name JSON mapping.')
    parser.add_argument('--destination', type=Path, default=Path(
        os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'playlite')
    args = parser.parse_args()
    features = json.loads(args.features.read_text()) if args.features else None
    games = import_snapshot(args.export, args.files, args.destination, features)
    print(f'Imported {len(games)} games into {args.destination}')
