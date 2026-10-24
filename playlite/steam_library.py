"""Read installed Steam games without changing Steam or game files."""
from pathlib import Path
from .desktop import host_environment


def read_vdf(path):
    import vdf
    with Path(path).open(encoding='utf-8', errors='replace') as stream:
        return vdf.load(stream)


def steam_roots():
    environment = host_environment()
    home = Path(environment.get('HOME') or Path.home())
    data = Path(environment.get('XDG_DATA_HOME') or home / '.local/share')
    candidates = [data / 'Steam', home / '.steam/steam', home / '.steam/root',
                  home / '.var/app/com.valvesoftware.Steam/data/Steam',
                  home / '.var/app/com.valvesoftware.Steam/.local/share/Steam']
    roots = []
    for path in candidates:
        if (path / 'steamapps').is_dir() and path.resolve() not in roots:
            roots.append(path.resolve())
    return roots


def library_folders(root):
    folders = [Path(root).resolve()]
    manifest = folders[0] / 'steamapps/libraryfolders.vdf'
    if manifest.is_file():
        try:
            values = read_vdf(manifest).get('libraryfolders', {})
            for key, value in values.items():
                if not str(key).isdigit():
                    continue
                location = value.get('path') if isinstance(value, dict) else value
                if location and Path(location).is_absolute():
                    path = Path(location).resolve()
                    if path not in folders:
                        folders.append(path)
        except (OSError, ValueError, SyntaxError, AttributeError, TypeError):
            pass
    return folders


def installed_game(manifest):
    manifest = Path(manifest).expanduser().resolve()
    data = read_vdf(manifest)['AppState']
    identity = str(data['appid'])
    if not identity.isascii() or not identity.isdigit() or int(identity) < 1:
        raise ValueError('Invalid Steam app ID.')
    identity = str(int(identity))
    if manifest.name != f'appmanifest_{identity}.acf':
        raise ValueError('Steam app ID does not match its manifest.')
    name = data['name'].strip()
    relative = Path(data['installdir'])
    common = (manifest.parent / 'common').resolve()
    directory = (common / relative).resolve()
    if not name or any(ord(c) < 32 for c in name):
        raise ValueError('Invalid Steam game name.')
    if relative.is_absolute() or not relative.parts or '..' in relative.parts or directory == common:
        raise ValueError('Invalid Steam installation folder.')
    if not int(data.get('StateFlags', '0')) & 4 or not directory.is_dir():
        raise ValueError('This Steam game is no longer installed.')
    if name.startswith(('Proton ', 'Steam Linux Runtime')) or identity == '228980':
        raise ValueError('Steam runtime tools are not games.')
    return {'name': name, 'app_id': identity, 'directory': directory, 'manifest': manifest}


def installed_games():
    games = {}
    folders = list(dict.fromkeys(folder for root in steam_roots() for folder in library_folders(root)))
    for folder in folders:
        for manifest in sorted((folder / 'steamapps').glob('appmanifest_*.acf')):
            try:
                game = installed_game(manifest)
                games.setdefault(game['app_id'], game)
            except (OSError, ValueError, SyntaxError, KeyError, TypeError, AttributeError):
                continue
    return sorted(games.values(), key=lambda game: game['name'].casefold())
