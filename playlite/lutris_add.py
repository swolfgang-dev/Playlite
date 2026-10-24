"""Create Wine entries in Lutris; never run or modify the selected executable."""
from contextlib import closing, contextmanager
from dataclasses import dataclass
from pathlib import Path
import re
import secrets
import sqlite3
import time
import uuid
import yaml
from .lutris_library import installations


def normalize_steam_id(steam_id):
    value = str(steam_id).strip()
    if not value.isascii() or not value.isdigit() or not 0 < int(value) <= (2**63 - 100) // 100:
        raise ValueError('Steam app ID cannot be encoded as a Lutris ID.')
    return str(int(value))


def steam_game_id(db, steam_id):
    """Use the Steam app ID followed by the first free two-digit entry number."""
    value = normalize_steam_id(steam_id)
    base = int(value) * 100
    for suffix in range(1, 100):
        identity = base + suffix
        if db.execute('SELECT 1 FROM games WHERE id=?', (identity,)).fetchone() is None:
            return identity
    raise ValueError(f'All Lutris entry numbers for Steam app {value} are in use.')


def random_game_id(db):
    for _ in range(1000):
        identity = (100000 + secrets.randbelow(900000)) * 10
        if db.execute('SELECT 1 FROM games WHERE id=?', (identity,)).fetchone() is None:
            return identity
    raise ValueError('Could not allocate an unused random Lutris ID. Try again.')


def prefix_slug(name):
    words = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', re.sub("['’]", '', name))
    words = re.sub(r'([A-Z])([A-Z][a-z])', r'\1-\2', words)
    return re.sub(r'[^\w]+', '-', words.casefold().replace('_', '-')).strip('-') or 'game'


def installation_folder(executable, root=''):
    executable = Path(executable).expanduser().resolve(strict=True)
    if root:
        root = Path(root).expanduser().resolve()
        try:
            relative = executable.relative_to(root)
            if len(relative.parts) > 1:
                return root / relative.parts[0]
        except ValueError:
            pass
    return executable.parent


@dataclass(frozen=True)
class ExecutablePlan:
    name: str
    executable: Path
    directory: Path
    prefix: Path
    database: Path
    steam_id: str = ''

    def validate(self):
        if self.steam_id not in (None, ''):
            normalize_steam_id(self.steam_id)
        if not self.name.strip() or any(ord(c) < 32 for c in self.name):
            raise ValueError('Enter a game name without control characters.')
        if not self.executable.is_absolute() or not self.executable.is_file() or self.executable.suffix.lower() != '.exe':
            raise ValueError('Choose an existing Windows .exe file.')
        if not self.directory.is_absolute() or not self.directory.is_dir() or not self.executable.resolve().is_relative_to(self.directory.resolve()):
            raise ValueError('The installation folder must contain the executable.')
        if not self.prefix.is_absolute() or (self.prefix.exists() and not self.prefix.is_dir()):
            raise ValueError('Choose an absolute Wine prefix folder path.')
        if not self.database.is_file():
            raise ValueError('Choose an existing Lutris library.')


def create_directories(path, created):
    missing = []
    while not path.exists():
        missing.append(path)
        path = path.parent
    for directory in reversed(missing):
        try:
            directory.mkdir()
        except FileExistsError:
            if not directory.is_dir():
                raise
        else:
            created.append(directory)


@contextmanager
def register_executable(plan):
    game = {'exe': str(plan.executable), 'prefix': str(plan.prefix),
            'working_dir': str(plan.executable.parent)}
    values = {'platform': 'Windows', 'executable': str(plan.executable), 'service': 'manual'}
    def duplicate(db, columns, directory):
        if db.execute('SELECT id FROM games WHERE executable=?', (str(plan.executable),)).fetchone():
            raise ValueError('This executable already has a Lutris entry. Import that entry instead.')
    with register_entry(plan, 'wine', game, values, duplicate, prefix=plan.prefix, steam_id=plan.steam_id) as action:
        yield action


@contextmanager
def register_entry(plan, runner, game, extra_values, check_duplicate, prefix=None, steam_id=None):
    """Share creation and compensation for core Wine and Steam entries."""
    plan.validate()
    database = plan.database.expanduser().resolve()
    installation = next((item for item in installations() if item['database'] == database), None)
    if installation is None:
        raise ValueError('Choose the active library of native or Flatpak Lutris.')
    config_name = prefix_slug(plan.name) + '-playlite-' + uuid.uuid4().hex[:8]
    config_directory = installation['config_directory'] / 'games'
    configuration = config_directory / (config_name + '.yml')
    configuration_data = {'game': game, 'playlite_id_scheme': 'steam' if steam_id not in (None, '') else 'random'}
    if steam_id not in (None, ''):
        configuration_data['playlite_steam_id'] = int(steam_id)
    content = yaml.safe_dump(configuration_data).encode()
    created = []
    wrote = False
    identity = None
    row = None
    committed = False
    try:
        with closing(sqlite3.connect(database.as_uri() + '?mode=rw', uri=True, timeout=5)) as db:
            db.row_factory = sqlite3.Row
            db.execute('BEGIN IMMEDIATE')
            try:
                columns = {column['name'] for column in db.execute('PRAGMA table_info(games)')}
                if not {'id', 'name', 'runner', 'configpath', 'executable'} <= columns:
                    raise ValueError('The Lutris library has an unsupported games table.')
                check_duplicate(db, columns, config_directory)
                allocated_id = steam_game_id(db, steam_id) if steam_id not in (None, '') else random_game_id(db)
                create_directories(configuration.parent, created)
                if prefix is not None:
                    create_directories(prefix, created)
                with configuration.open('xb') as stream:
                    wrote = True
                    stream.write(content)
                values = {'id': allocated_id, 'name': plan.name.strip(), 'sortname': plan.name.strip(),
                          'slug': prefix_slug(plan.name), 'runner': runner,
                          'directory': str(plan.directory), 'installed': 1,
                          'installed_at': int(time.time()), 'configpath': config_name,
                          'playtime': 0, **extra_values}
                values = {key: value for key, value in values.items() if key in columns}
                fields = ','.join(values)
                placeholders = ','.join('?' for _ in values)
                identity = db.execute(f'INSERT INTO games ({fields}) VALUES ({placeholders})', list(values.values())).lastrowid
                row = dict(db.execute('SELECT * FROM games WHERE id=?', (identity,)).fetchone())
                db.commit()
                committed = True
            except BaseException:
                db.rollback()
                raise
        try:
            yield {'Name': plan.name.strip(), 'Integration': 'LutrisIntegration',
                   'GameId': str(identity), 'LutrisDatabase': str(database)}
        except BaseException:
            with closing(sqlite3.connect(database.as_uri() + '?mode=rw', uri=True, timeout=5)) as db:
                db.row_factory = sqlite3.Row
                db.execute('BEGIN IMMEDIATE')
                current = db.execute('SELECT * FROM games WHERE id=?', (identity,)).fetchone()
                if (current is None or dict(current) != row or configuration.is_symlink()
                        or not configuration.is_file() or configuration.read_bytes() != content):
                    raise ValueError('The new Lutris entry changed after registration; it was retained for recovery.')
                db.execute('DELETE FROM games WHERE id=?', (identity,))
                db.commit()
            identity = None
            raise
    finally:
        if not committed or identity is None:
            if wrote:
                configuration.unlink(missing_ok=True)
            for directory in reversed(created):
                try:
                    directory.rmdir()
                except OSError:
                    pass


class PendingExecutable:
    def __init__(self, plan):
        self.plan = plan

    def details(self):
        details = [('Entry', self.plan.name), ('Runner', 'Wine'),
                   ('Executable', str(self.plan.executable)), ('Wine prefix', str(self.plan.prefix))]
        if self.plan.steam_id:
            details.append(('Steam app ID', self.plan.steam_id))
        return details

    @contextmanager
    def commit_action(self, action, providers):
        from dataclasses import replace
        plan = replace(self.plan, name=action['Name'])
        with register_executable(plan) as registered:
            yield dict(action, GameId=registered['GameId'], LutrisDatabase=registered['LutrisDatabase'])
