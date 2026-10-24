"""Read existing Lutris entries without modifying their library or configuration."""
from contextlib import closing
import configparser
import json
from pathlib import Path
import sqlite3
import uuid
from .desktop import host_environment


def installations():
    environment = host_environment()
    home = Path(environment.get('HOME') or Path.home())
    data = Path(environment.get('XDG_DATA_HOME') or home / '.local/share')
    config = Path(environment.get('XDG_CONFIG_HOME') or home / '.config')
    flatpak = home / '.var/app/net.lutris.Lutris'
    result = []
    for data_root, config_root, is_flatpak in [(data / 'lutris', config / 'lutris', False),
                                             (flatpak / 'data/lutris', flatpak / 'config/lutris', True)]:
        if not config_root.exists():
            config_root = data_root
        settings = configparser.ConfigParser()
        try:
            settings.read(config_root / 'lutris.conf')
            selected = settings.get('lutris', 'pga_path', fallback='')
        except (configparser.Error, OSError, UnicodeError) as error:
            raise ValueError('Could not read Lutris library settings: ' + str(error)) from error
        database = Path(selected).expanduser() if selected else data_root / 'pga.db'
        result.append({'database': database.resolve(), 'flatpak': is_flatpak,
                       'config_directory': config_root.resolve()})
    return result


def library_databases():
    return list(dict.fromkeys(item['database'] for item in installations() if item['database'].is_file()))


def read_entries(database):
    database = Path(database).expanduser().resolve()
    if not database.is_file():
        raise ValueError('Lutris library not found. Open Lutris first or choose its pga.db file.')
    try:
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute('SELECT * FROM games ORDER BY name COLLATE NOCASE, id').fetchall()
    except sqlite3.Error as error:
        raise ValueError('Could not read the Lutris library: ' + str(error)) from error
    entries = []
    for row in rows:
        values = dict(row)
        if not isinstance(values.get('id'), int) or values['id'] < 1:
            continue
        name = str(values.get('name') or '').strip()
        if name:
            entry = {'id': str(values['id']), 'name': name,
                     'installed': bool(values.get('installed')), 'database': str(database)}
            directory = values.get('directory')
            if isinstance(directory, str) and directory and Path(directory).expanduser().is_absolute():
                entry['directory'] = str(Path(directory).expanduser())
            entries.append(entry)
    return entries


def is_linked(game, entry):
    if 'PlayActions' in game:
        links = game.get('PlayActions') or []
    else:
        links = [{'Integration': 'LutrisIntegration', 'GameId': game.get('LutrisId')}]
    for action in links:
        if action.get('Integration') != 'LutrisIntegration' or str(action.get('GameId')) != entry['id']:
            continue
        database = action.get('LutrisDatabase')
        if not database or str(Path(database).expanduser().resolve()) == entry['database']:
            return True
    return False


def import_entry(data, games, database, identity, *, metadata_ids=None):
    """Recheck the selection and duplicates inside the Playlite library transaction."""
    from .library_storage import library_lock
    from .game_storage import save_game
    database = Path(database).expanduser().resolve()
    if not any(item['database'] == database for item in installations()):
        raise ValueError('Choose the active library of native or Flatpak Lutris so imported games can launch.')
    entry = next((entry for entry in read_entries(database) if entry['id'] == str(identity)), None)
    if entry is None:
        raise ValueError('This Lutris entry no longer exists. Refresh the list and select another entry.')
    with library_lock(data):
        path = Path(data) / 'library.json'
        current = json.loads(path.read_text()) if path.exists() else games
        if any(is_linked(game, entry) for game in current):
            raise ValueError('This Lutris entry is already in your Playlite library.')
        game = {'Id': str(uuid.uuid4()), 'Name': entry['name'], 'Source': 'Lutris',
                'Platforms': [], 'IsInstalled': entry['installed'],
                'GameProvider': 'LutrisIntegration',
                'PlayActions': [{'Name': 'Play', 'Integration': 'LutrisIntegration',
                                 'GameId': entry['id'], 'LutrisDatabase': entry['database']}]}
        if entry.get('directory'):
            game['InstallDirectory'] = entry['directory']
        if metadata_ids:
            game['MetadataIds'] = dict(metadata_ids)
        return save_game(Path(data), current, game), game['Id']


def entry_details(database, identity):
    """Read runner-specific details afresh; these values never become overrides."""
    import yaml
    database = Path(database).expanduser().resolve()
    if not database.is_file():
        raise ValueError('Lutris library not found.')
    try:
        with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute('SELECT * FROM games WHERE id=?', (str(identity),)).fetchone()
    except sqlite3.Error as error:
        raise ValueError('Could not read Lutris entry details: ' + str(error)) from error
    if row is None:
        raise ValueError('The selected Lutris entry no longer exists.')
    row = dict(row)
    configuration = {}
    config_name = row.get('configpath')
    if config_name:
        if not isinstance(config_name, str) or '/' in config_name or '\\' in config_name or config_name in ('.', '..'):
            raise ValueError('The Lutris entry has an invalid configuration filename.')
        installation = next((item for item in installations() if item['database'] == database), None)
        directory = installation['config_directory'] if installation else database.parent
        path = directory / 'games' / (config_name + '.yml')
        try:
            configuration = yaml.safe_load(path.read_text()) or {}
        except (OSError, yaml.YAMLError) as error:
            raise ValueError('Could not read the Lutris entry configuration: ' + str(error)) from error
        if not isinstance(configuration, dict) or not isinstance(configuration.get('game', {}), dict):
            raise ValueError('The Lutris entry configuration has invalid game settings.')
    runner = row.get('runner') or configuration.get('runner') or ''
    game = configuration.get('game') or {}
    details = [('Entry', str(row.get('name') or '')), ('Runner', str(runner).capitalize() or 'Unknown')]
    if runner == 'steam':
        app_id = game.get('appid') or (row.get('service_id') if row.get('service') == 'steam' else '')
        details.append(('Steam app ID', str(app_id or 'Not set')))
    elif runner == 'wine':
        details.extend([('Executable', str(game.get('exe') or row.get('executable') or 'Not set')),
                        ('Wine prefix', str(game.get('prefix') or 'Not set'))])
        if configuration.get('playlite_steam_id'):
            details.append(('Steam app ID', str(configuration['playlite_steam_id'])))
    elif runner == 'linux':
        details.append(('Executable', str(game.get('exe') or row.get('executable') or 'Not set')))
    return details


def configuration_path(database, identity):
    """Locate a saved entry configuration for core and optional action controls."""
    if not str(identity).isascii() or not str(identity).isdigit() or int(identity) < 1:
        raise ValueError('Save a valid Lutris entry before changing its settings.')
    if not database:
        databases = library_databases()
        if len(databases) != 1:
            raise ValueError('Select a Lutris library for this play action.')
        database = databases[0]
    database = Path(database).expanduser().resolve()
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as connection:
        row = connection.execute('SELECT configpath FROM games WHERE id=?', (int(identity),)).fetchone()
    name = row[0] if row else None
    if not isinstance(name, str) or not name or name in ('.', '..') or '/' in name or '\\' in name:
        raise ValueError('The selected Lutris entry has no valid configuration.')
    installation = next((item for item in installations() if item['database'] == database), None)
    root = installation['config_directory'] if installation else database.parent
    path = root / 'games' / (name + '.yml')
    if path.is_symlink() or not path.is_file() or path.resolve().parent != (root / 'games').resolve():
        raise ValueError('The selected Lutris configuration is missing or unsafe.')
    return path
