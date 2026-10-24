"""Required Lutris runtime and library association contract."""
import shutil
import subprocess
from .desktop import host_environment


def require_lutris():
    environment = host_environment()
    path = environment.get('PATH', '')
    if shutil.which('lutris', path=path):
        return
    flatpak = shutil.which('flatpak', path=path)
    if flatpak:
        try:
            result = subprocess.run([flatpak, 'info', 'net.lutris.Lutris'], env=environment,
                                    capture_output=True, timeout=10)
            if result.returncode == 0:
                return
        except (OSError, subprocess.TimeoutExpired):
            pass
    raise ValueError('Playlite requires Lutris. Install Lutris before starting Playlite.')


def validate_lutris_association(game):
    """Require every saved game and action to reference a Lutris entry."""
    if 'PlayActions' in game:
        actions = game.get('PlayActions') or []
    elif game.get('GameProvider') in (None, 'LutrisIntegration') and game.get('LutrisId'):
        actions = [{'Integration': 'LutrisIntegration', 'GameId': game['LutrisId']}]
    else:
        actions = []
    if not actions:
        raise ValueError('Every game needs an associated Lutris entry.')
    for action in actions:
        identity = str(action.get('GameId') or '')
        if (action.get('Integration') != 'LutrisIntegration' or not identity.isascii()
                or not identity.isdigit() or int(identity) < 1):
            raise ValueError('Every play action must select a valid Lutris entry ID.')
