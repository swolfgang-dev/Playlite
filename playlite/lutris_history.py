"""Display history from the linked Lutris entries without counting sessions twice."""
from contextlib import closing, contextmanager, ExitStack
import copy
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from .lutris_ids import links, database_for
from . import lutris_library


def linked_entries(game, available):
    result = set()
    for action in links(game):
        if action.get('Integration') != 'LutrisIntegration':
            continue
        database = database_for(action, available)
        identity = str(action.get('GameId') or '')
        if database is not None and identity.isascii() and identity.isdigit() and int(identity) > 0:
            result.add((database, int(identity)))
    return result


def refresh_history(data, games):
    from .library_storage import library_lock
    from .storage import atomic_json
    data = Path(data)
    with library_lock(data):
        path = data / 'library.json'
        current = json.loads(path.read_text()) if path.exists() else copy.deepcopy(games)
        available = lutris_library.installations()
        cache = {}
        changed = False
        for game in current:
            entries = linked_entries(game, available)
            if not entries:
                continue
            histories = []
            for database, identity in entries:
                if database not in cache:
                    try:
                        with closing(sqlite3.connect(database.as_uri()+'?mode=ro', uri=True, timeout=.2)) as db:
                            cache[database] = {row[0]: row[1:] for row in db.execute('SELECT id,playtime,lastplayed FROM games')}
                    except sqlite3.Error:
                        cache[database] = {}
                if identity in cache[database]:
                    histories.append(cache[database][identity])
            # A missing library or deleted entry must not erase saved history.
            if len(histories) != len(entries):
                continue
            seconds = round(sum(max(0, float(row[0] or 0)) for row in histories) * 3600)
            last = max((int(row[1] or 0) for row in histories), default=0)
            stamp = datetime.fromtimestamp(last).astimezone().isoformat(timespec='seconds') if last else None
            if game.get('Playtime') != seconds or game.get('LastActivity') != stamp:
                game.update(Playtime=seconds, LastActivity=stamp)
                changed = True
        if changed and path.exists():
            atomic_json(path, current)
        return current


@contextmanager
def reset_database(database, identities):
    with closing(sqlite3.connect(database.as_uri()+'?mode=rw', uri=True, timeout=5)) as db:
        db.execute('BEGIN IMMEDIATE')
        originals = []
        try:
            for identity in sorted(identities):
                row = db.execute('SELECT playtime,lastplayed FROM games WHERE id=?', (identity,)).fetchone()
                if row is None:
                    raise ValueError('A linked Lutris entry no longer exists. Refresh your library before clearing history.')
                originals.append((identity, *row))
                db.execute('UPDATE games SET playtime=0,lastplayed=NULL WHERE id=?', (identity,))
            db.commit()
        except BaseException:
            db.rollback()
            raise
        try:
            yield
        except BaseException:
            with db:
                for identity, playtime, lastplayed in originals:
                    db.execute('UPDATE games SET playtime=?,lastplayed=? WHERE id=? AND playtime=0 AND lastplayed IS NULL',
                               (playtime, lastplayed, identity))
            raise


@contextmanager
def reset_history(games):
    grouped = {}
    available = lutris_library.installations()
    for game in games:
        for database, identity in linked_entries(game, available):
            grouped.setdefault(database, set()).add(identity)
    try:
        with ExitStack() as pending:
            for database, identities in sorted(grouped.items()):
                pending.enter_context(reset_database(database, identities))
            yield
    except sqlite3.Error as error:
        raise ValueError('Could not reset linked Lutris history: ' + str(error)) from error
