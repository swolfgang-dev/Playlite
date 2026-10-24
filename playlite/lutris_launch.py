"""Dispatch core play actions to the Lutris installation owning their entry."""
from pathlib import Path
import shutil
import subprocess
from .desktop import host_environment
from .lutris_library import installations, read_entries
from .lutris_requirement import validate_lutris_association

APP_ID = 'net.lutris.Lutris'


def resolve_action(action):
    validate_lutris_association({'PlayActions': [action]})
    database = action.get('LutrisDatabase')
    available = installations()
    if database:
        database = Path(database).expanduser().resolve()
    else:
        candidates = [item['database'] for item in available if item['database'].is_file()]
        if len(candidates) != 1:
            raise ValueError('Select a Lutris entry and library for this play action.')
        database = candidates[0]
    installation = next((item for item in available if item['database'] == database), None)
    if installation is None:
        raise ValueError('This database is not the active library of native or Flatpak Lutris. Select an entry from your active Lutris library.')
    entry = next((entry for entry in read_entries(database) if entry['id'] == str(action['GameId'])), None)
    if entry is None:
        raise ValueError('The selected Lutris entry no longer exists. Choose another entry for this play action.')
    return installation, entry


def launch_action(action):
    installation, entry = resolve_action(action)
    environment = host_environment()
    executable = shutil.which('flatpak' if installation['flatpak'] else 'lutris', path=environment.get('PATH', ''))
    if not executable:
        raise ValueError('The Lutris installation for this entry is unavailable.')
    uri = 'lutris:rungameid/' + entry['id']
    if installation['flatpak']:
        try:
            check = subprocess.run([executable, 'info', APP_ID], env=environment, capture_output=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError('Could not check the Flatpak Lutris installation.') from error
        if check.returncode:
            raise ValueError('Flatpak Lutris is not installed for this library.')
        command = [executable, 'run', APP_ID, uri]
    else:
        command = [executable, uri]
    return subprocess.Popen(command, env=environment, start_new_session=True)
