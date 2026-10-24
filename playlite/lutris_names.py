"""Keep linked action names in sync without changing entry IDs or config paths."""
from contextlib import closing, contextmanager, ExitStack
import copy
import json
from pathlib import Path
import sqlite3
from .lutris_ids import links, database_for
from . import lutris_library


def action_link(action):
    if action.get('Integration') != 'LutrisIntegration':return None
    database = database_for(action, lutris_library.installations())
    return (database, str(action.get('GameId'))) if database is not None else None


@contextmanager
def save_name(updated, previous):
    game = copy.deepcopy(updated)
    game.pop('LutrisName', None)  # Remove the obsolete library-title baseline.
    with ExitStack() as pending:
        actions = game.get('PlayActions') or []
        for index, action in enumerate(actions):
            actions[index] = pending.enter_context(save_action_name(action))
        yield game


@contextmanager
def save_action_name(updated):
    game = copy.deepcopy(updated)
    link = action_link(game)
    if link is None:
        game.pop('LutrisName', None)
        yield game
        return
    database, identity = link
    changed = False
    with closing(sqlite3.connect(database.as_uri()+'?mode=rw', uri=True, timeout=5)) as db:
        try:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT name FROM games WHERE id=?', (identity,)).fetchone()
            if row is None:raise ValueError('The linked Lutris entry no longer exists.')
            old = row[0]
            baseline = game.get('LutrisName')
            name = game.get('Name', '').strip()
            if not name:raise ValueError('Enter a game name.')
            if name == baseline or baseline is None and name == 'Play':
                name = old  # An untouched editor must retain a newer Lutris title.
            columns = {row[1] for row in db.execute('PRAGMA table_info(games)')}
            sort = db.execute('SELECT sortname FROM games WHERE id=?', (identity,)).fetchone()[0] if 'sortname' in columns else None
            changed = name != old
            if changed:
                if 'sortname' in columns and sort == old:
                    db.execute('UPDATE games SET name=?,sortname=? WHERE id=?', (name,name,identity))
                else:
                    db.execute('UPDATE games SET name=? WHERE id=?', (name,identity))
            db.commit()
        except BaseException:
            db.rollback()
            raise
        game['Name'] = name
        game['LutrisName'] = name
        try:
            yield game
        except BaseException:
            if changed:
                db.execute('BEGIN IMMEDIATE')
                if 'sortname' in columns and sort == old:
                    db.execute('UPDATE games SET name=?,sortname=? WHERE id=? AND name=? AND sortname=?', (old,sort,identity,name,name))
                else:
                    db.execute('UPDATE games SET name=? WHERE id=? AND name=?', (old,identity,name))
                db.commit()
            raise


def refresh_names(data, games):
    """Read Lutris titles and merge only action names into the latest Playlite library."""
    from .library_storage import library_lock
    from .storage import atomic_json
    data = Path(data)
    with library_lock(data):
        path = data/'library.json'
        current = json.loads(path.read_text()) if path.exists() else copy.deepcopy(games)
        cache = {}
        changed = False
        for game in current:
            if 'LutrisName' in game:
                game.pop('LutrisName');changed = True
            for action in game.get('PlayActions') or []:
                link = action_link(action)
                if link is None:continue
                database, identity = link
                if database not in cache:
                    try:
                        with closing(sqlite3.connect(database.as_uri()+'?mode=ro', uri=True, timeout=.2)) as db:
                            cache[database] = {str(row[0]):row[1] for row in db.execute('SELECT id,name FROM games')}
                    except sqlite3.Error:
                        cache[database] = {}
                name = cache[database].get(identity)
                if not isinstance(name,str) or not name.strip():continue
                baseline = action.get('LutrisName')
                local = action.get('Name')
                # Retain existing custom action labels until the user saves them.
                if baseline is None and local not in (None, '', 'Play', name):
                    action['LutrisName'] = name;changed = True
                    continue
                if baseline is not None and local != baseline:continue
                if local != name or baseline != name:
                    action['Name'] = action['LutrisName'] = name
                    changed = True
        if changed and path.exists():atomic_json(path,current)
    return current
