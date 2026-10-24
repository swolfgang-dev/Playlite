"""Migrate random Lutris IDs when Steam associations become known."""
import copy
from contextlib import closing, contextmanager, ExitStack
from pathlib import Path
import sqlite3
import yaml
from . import lutris_library
from .lutris_add import normalize_steam_id, steam_game_id
from .storage import atomic_bytes


def links(game):
    if 'PlayActions' in game:
        return game.get('PlayActions') or []
    if game.get('LutrisId'):
        return [{'Integration': 'LutrisIntegration', 'GameId': str(game['LutrisId']),
                 'LutrisDatabase': game.get('LutrisDatabase', '')}]
    return []


def database_for(action, available):
    value = action.get('LutrisDatabase')
    if value:
        return Path(value).expanduser().resolve()
    databases = list(dict.fromkeys(item['database'] for item in available if item['database'].is_file()))
    return databases[0] if len(databases) == 1 else None


def rewrite_links(game, replacements):
    for action in links(game):
        if action.get('Integration') != 'LutrisIntegration':
            continue
        for change in replacements:
            database = action.get('LutrisDatabase')
            if (str(action.get('GameId')) == str(change['old']) and
                    (not database or Path(database).expanduser().resolve() == change['database'])):
                action['GameId'] = str(change['new'])
                action['LutrisDatabase'] = str(change['database'])
                if 'PlayActions' not in game:
                    game['LutrisId'] = change['new']
                    game['LutrisDatabase'] = str(change['database'])
                break


def configuration(row, directory):
    name = row.get('configpath')
    if not isinstance(name, str) or not name or '/' in name or '\\' in name or name in ('.', '..'):
        raise ValueError('The Lutris entry has an invalid configuration filename.')
    path = directory / (name + '.yml')
    if path.is_symlink():
        raise ValueError('Cannot migrate a symlinked Lutris configuration.')
    original = path.read_bytes()
    try:
        data = yaml.safe_load(original)
    except yaml.YAMLError as error:
        raise ValueError('Could not read the Lutris entry configuration.') from error
    if not isinstance(data, dict) or not isinstance(data.get('game', {}), dict):
        raise ValueError('The Lutris entry has invalid game settings.')
    return path, original, data


def rekey(db, old, new):
    # Lutris uses game_id in its association tables; also honor declared FKs.
    references = set()
    for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        quoted = '"' + table.replace('"', '""') + '"'
        columns = {row[1] for row in db.execute('PRAGMA table_info('+quoted+')')}
        if 'game_id' in columns:
            references.add((quoted, '"game_id"'))
        for foreign in db.execute('PRAGMA foreign_key_list('+quoted+')'):
            if foreign[2] == 'games' and foreign[4] in ('id', None):
                references.add((quoted, '"'+foreign[3].replace('"', '""')+'"'))
    db.execute('PRAGMA defer_foreign_keys=ON')
    db.execute('UPDATE games SET id=? WHERE id=?', (new, old))
    for table, column in references:
        db.execute(f'UPDATE {table} SET {column}=? WHERE {column}=?', (new, old))


def normalized_folder(value):
    return str(Path(value).expanduser().resolve()) if value else ''


@contextmanager
def migrate_database(installation, action_ids, metadata_id, installation_folder):
    database = installation['database']
    directory = installation['config_directory'] / 'games'
    changes = []
    with closing(sqlite3.connect(database.as_uri()+'?mode=rw', uri=True, timeout=5)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN IMMEDIATE')
        try:
            rows = [dict(row) for row in db.execute('SELECT * FROM games ORDER BY id')]
            selected = [row for row in rows if str(row['id']) in action_ids]
            targets = {}
            explicit = normalize_steam_id(metadata_id) if metadata_id else ''
            if explicit:
                for row in selected:
                    folder = normalized_folder(row.get('directory'))
                    if folder:
                        targets.setdefault(folder, set()).add(explicit)
                if installation_folder:
                    targets.setdefault(normalized_folder(installation_folder), set()).add(explicit)
            else:
                for row in selected:
                    name = row.get('configpath')
                    if (not isinstance(name, str) or not name or '/' in name or '\\' in name
                            or name in ('.', '..') or not (directory / (name+'.yml')).is_file()):
                        continue
                    _, _, data = configuration(row, directory)
                    app_id = data.get('playlite_steam_id')
                    if not app_id and row.get('runner') == 'steam':
                        app_id = (data.get('game') or {}).get('appid')
                    if app_id and row.get('directory'):
                        targets.setdefault(normalized_folder(row['directory']), set()).add(normalize_steam_id(app_id))
            known_ids = set().union(*targets.values()) if targets else set()
            for row in rows:
                old = row['id']
                if not isinstance(old, int) or old < 1000000 or old % 10:
                    continue
                candidates = {explicit} if explicit and str(old) in action_ids else targets.get(normalized_folder(row.get('directory')), set())
                if not candidates and str(old) in action_ids and len(known_ids) == 1:
                    candidates = known_ids
                if not candidates:
                    continue
                path, original, data = configuration(row, directory)
                if data.get('playlite_id_scheme') != 'random' or data.get('playlite_steam_id'):
                    continue
                if len(candidates) != 1:
                    raise ValueError('Conflicting Steam associations for this Lutris game folder.')
                app_id = next(iter(candidates))
                new = steam_game_id(db, app_id)
                data['playlite_id_scheme'] = 'steam'
                data['playlite_steam_id'] = int(app_id)
                written = yaml.safe_dump(data).encode()
                change = {'database': database, 'old': old, 'new': new,
                          'path': path, 'original': original, 'written': written,
                          'before': row, 'after': dict(row, id=new)}
                changes.append(change)
                atomic_bytes(path, written)
                rekey(db, old, new)
            db.commit()
        except BaseException:
            db.rollback()
            for change in reversed(changes):
                atomic_bytes(change['path'], change['original'])
            raise
    try:
        yield changes
    except BaseException:
        if changes:
            with closing(sqlite3.connect(database.as_uri()+'?mode=rw', uri=True, timeout=5)) as db:
                db.row_factory = sqlite3.Row
                db.execute('BEGIN IMMEDIATE')
                for change in reversed(changes):
                    row = db.execute('SELECT * FROM games WHERE id=?', (change['new'],)).fetchone()
                    if (row is None or dict(row) != change['after'] or
                            db.execute('SELECT 1 FROM games WHERE id=?', (change['old'],)).fetchone() or
                            change['path'].is_symlink() or change['path'].read_bytes() != change['written']):
                        raise ValueError(f'Lutris entry {change["new"]} changed externally; it was retained instead of restoring ID {change["old"]}.')
                    rekey(db, change['new'], change['old'])
                db.commit()
            for change in reversed(changes):
                atomic_bytes(change['path'], change['original'])
        raise


@contextmanager
def migrate_steam_ids(updated):
    available = lutris_library.installations()
    grouped = {}
    for action in links(updated):
        if action.get('Integration') == 'LutrisIntegration':
            database = database_for(action, available)
            if database is not None:
                grouped.setdefault(database, set()).add(str(action.get('GameId')))
    metadata_id = (updated.get('MetadataIds') or {}).get('SteamMetadata') or ''
    original = copy.deepcopy(updated)
    changes = []
    try:
        with ExitStack() as pending:
            for database, action_ids in sorted(grouped.items()):
                installation = next((item for item in available if item['database'] == database), None)
                if installation is None:
                    continue
                changes.extend(pending.enter_context(migrate_database(installation, action_ids, metadata_id, updated.get('InstallDirectory'))))
            rewrite_links(updated, changes)
            yield changes
    except BaseException:
        updated.clear()
        updated.update(original)
        raise
