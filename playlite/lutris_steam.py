"""Create Lutris Steam-runner entries for installed Steam games."""
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
import yaml
from .steam_library import installed_game
from .lutris_add import register_entry


@dataclass(frozen=True)
class SteamPlan:
    name: str
    app_id: str
    directory: Path
    manifest: Path
    database: Path

    def validate(self):
        if not self.name.strip() or any(ord(c) < 32 for c in self.name):
            raise ValueError('Enter a game name without control characters.')
        try:
            game = installed_game(self.manifest)
        except (OSError, ValueError, SyntaxError, KeyError, TypeError, AttributeError) as error:
            raise ValueError('This Steam game is no longer installed. Refresh the list.') from error
        if game['app_id'] != self.app_id or game['directory'] != self.directory.resolve():
            raise ValueError('The Steam installation changed. Refresh the list.')
        if not self.database.is_file():
            raise ValueError('Choose an existing Lutris library.')


def check_duplicate(app_id, db, columns, config_directory):
    for record in db.execute("SELECT * FROM games WHERE runner='steam'"):
        row = dict(record)
        if str(row.get('service_id') or '') == app_id:
            raise ValueError('This Steam game already has a Lutris entry. Import that entry instead.')
        name = row.get('configpath')
        if not isinstance(name, str) or not name or '/' in name or '\\' in name or name in ('.', '..'):
            continue
        path = config_directory / (name + '.yml')
        if not path.is_file():
            continue
        try:
            config = yaml.safe_load(path.read_text()) or {}
            identity = str((config.get('game') or {}).get('appid') or '')
        except (OSError, yaml.YAMLError, AttributeError, TypeError) as error:
            raise ValueError('Could not check an existing Lutris Steam entry: '+str(error)) from error
        if identity == app_id:
            raise ValueError('This Steam game already has a Lutris entry. Import that entry instead.')


@contextmanager
def register_steam(plan):
    def duplicate(db, columns, directory):
        check_duplicate(plan.app_id, db, columns, directory)
    with register_entry(plan, 'steam', {'appid': plan.app_id},
                        {'executable': '', 'service': 'steam', 'service_id': plan.app_id}, duplicate, steam_id=plan.app_id) as action:
        yield action


class PendingSteam:
    def __init__(self, plan):
        self.plan = plan

    def details(self):
        return [('Entry', self.plan.name), ('Runner', 'Steam'), ('Steam app ID', self.plan.app_id)]

    @contextmanager
    def commit_action(self, action, providers):
        with register_steam(replace(self.plan, name=action['Name'])) as registered:
            yield dict(action, GameId=registered['GameId'], LutrisDatabase=registered['LutrisDatabase'])
