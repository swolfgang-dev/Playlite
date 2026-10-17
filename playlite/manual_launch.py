"""Launch user-selected executables directly, without a launcher integration."""
import os
from pathlib import Path
import shlex
import subprocess

from .desktop import host_environment
from .providers import GameProvider
from . import __version__


class ManualLaunch(GameProvider):
    id = 'Manual'
    name = 'Manual'
    type = 'game'
    version = __version__
    action_id_field = 'ManualGameId'

    def create_action_editor(self, action, parent=None):
        from .play_actions import LaunchSettings
        return LaunchSettings(action, parent, hide_prefix=True)

    def validate_action(self, action):
        executable = Path(action.get('Executable') or '')
        if not executable.is_absolute() or not executable.is_file():
            raise ValueError('Select an existing executable or launcher script for the Manual action.')
        if not os.access(executable, os.X_OK):
            raise ValueError('The Manual executable must have execute permission. For Windows games, select a runner or launcher script.')
        shlex.split(action.get('Arguments') or '')
        directory = action.get('InstallDirectory')
        if directory and not Path(directory).is_dir():
            raise ValueError('Select an existing working folder for the Manual action.')

    def launch(self, game):
        action = dict(Executable=game.get('Executable'), Arguments=game.get('LaunchArguments'),
                      InstallDirectory=game.get('InstallDirectory'))
        self.validate_action(action)
        executable = action['Executable']
        return subprocess.Popen([executable, *shlex.split(action.get('Arguments') or '')],
                                cwd=action.get('InstallDirectory') or str(Path(executable).parent),
                                start_new_session=True, env=host_environment())
