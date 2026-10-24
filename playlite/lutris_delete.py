"""Remove explicitly selected launcher records while keeping installed game data."""
from contextlib import closing, contextmanager, ExitStack
import sqlite3
from . import lutris_library
from .lutris_history import linked_entries
from .storage import atomic_bytes


def associated_entries(game):
    return linked_entries(game, lutris_library.installations())


def quote(identifier):
    return '"' + identifier.replace('"', '""') + '"'


@contextmanager
def delete_database(database, identities):
    installation = next((item for item in lutris_library.installations() if item['database'] == database), None)
    directory = (installation['config_directory'] if installation else database.parent) / 'games'
    removed = []
    files = []
    with closing(sqlite3.connect(database.as_uri()+'?mode=rw', uri=True, timeout=5)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN IMMEDIATE')
        try:
            references = set()
            for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
                if table == 'games':
                    continue
                if any(row[1] == 'game_id' for row in db.execute('PRAGMA table_info('+quote(table)+')')):
                    references.add((table, 'game_id'))
                for foreign in db.execute('PRAGMA foreign_key_list('+quote(table)+')'):
                    if foreign[2] == 'games' and foreign[4] in ('id', None):
                        references.add((table, foreign[3]))
            for identity in sorted(identities):
                row = db.execute('SELECT * FROM games WHERE id=?', (identity,)).fetchone()
                if row is None:
                    continue
                row = dict(row)
                name = row.get('configpath')
                if name:
                    if not isinstance(name, str) or '/' in name or '\\' in name or name in ('.', '..'):
                        raise ValueError('The Lutris entry has an unsafe configuration filename.')
                    # A shared configuration must survive deletion of one entry.
                    shared = db.execute('SELECT 1 FROM games WHERE configpath=? AND id!=?', (name, identity)).fetchone()
                    path = directory / (name+'.yml')
                    if not shared and (path.exists() or path.is_symlink()):
                        if path.is_symlink() or path.resolve().parent != directory.resolve() or not path.is_file():
                            raise ValueError('Cannot delete an unsafe Lutris configuration.')
                        files.append((path, path.read_bytes(), path.stat().st_mode & 0o777))
                for table, column in sorted(references):
                    rows = [dict(item) for item in db.execute('SELECT * FROM '+quote(table)+' WHERE '+quote(column)+'=?', (identity,))]
                    removed.extend((table, item) for item in rows)
                    db.execute('DELETE FROM '+quote(table)+' WHERE '+quote(column)+'=?', (identity,))
                removed.append(('games', row))
                db.execute('DELETE FROM games WHERE id=?', (identity,))
            for path, _, _ in files:
                path.unlink()
            db.commit()
        except BaseException:
            db.rollback()
            for path, content, mode in files:
                if not path.exists():
                    atomic_bytes(path, content, mode=mode)
            raise
        try:
            yield
        except BaseException:
            # Never overwrite an entry recreated by another launcher while saving.
            with db:
                for table, row in reversed(removed):
                    columns = list(row)
                    db.execute('INSERT INTO '+quote(table)+' ('+','.join(map(quote, columns))+') VALUES ('+','.join('?' for _ in columns)+')',
                               [row[column] for column in columns])
            for path, content, mode in files:
                if not path.exists():
                    atomic_bytes(path, content, mode=mode)
            raise


@contextmanager
def delete_entries(games, remaining):
    available = lutris_library.installations()
    retained = set().union(*(linked_entries(game, available) for game in remaining)) if remaining else set()
    grouped = {}
    for game in games:
        for database, identity in linked_entries(game, available) - retained:
            grouped.setdefault(database, set()).add(identity)
    with ExitStack() as pending:
        for database, identities in sorted(grouped.items()):
            pending.enter_context(delete_database(database, identities))
        yield
