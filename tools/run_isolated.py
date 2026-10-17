"""Run source Playlite with a disposable profile and locally copied plugins."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from check_workspace import CORE, copy_plugin_fixtures, isolated_environment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshot', type=Path, help='Render offscreen to this file, then exit.')
    parser.add_argument('--core-only', action='store_true')
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix='playlite-preview-') as temporary:
        environment = isolated_environment(Path(temporary))
        # Keep repository resource identities and disable the installed updater.
        # Host-restore helpers still point exclusively to temporary roots.
        environment['PLAYLITE_PROFILE'] = 'repo'
        if not args.core_only:
            copy_plugin_fixtures(Path(environment['XDG_DATA_HOME']) / 'playlite/plugins')
        command = [sys.executable, '-c', 'from playlite.app import main; main()']
        if args.screenshot:
            command.extend(['--screenshot', str(args.screenshot.absolute())])
        else:
            # Share only the display connection with the desktop.
            if os.environ.get('WAYLAND_DISPLAY'):
                display = Path(os.environ['WAYLAND_DISPLAY'])
                if not display.is_absolute():
                    display = Path(os.environ['XDG_RUNTIME_DIR']) / display
                environment.update(QT_QPA_PLATFORM='wayland', WAYLAND_DISPLAY=str(display))
            elif os.environ.get('DISPLAY'):
                environment.update(QT_QPA_PLATFORM='xcb', DISPLAY=os.environ['DISPLAY'])
                if os.environ.get('XAUTHORITY'):
                    environment['XAUTHORITY'] = os.environ['XAUTHORITY']
            else:
                parser.error('No display available; use --screenshot PATH for offscreen review.')
        print('Disposable profile: ' + temporary, flush=True)
        return subprocess.run(command, cwd=CORE, env=environment).returncode


if __name__ == '__main__':
    sys.exit(main())
