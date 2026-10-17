"""Run core and sibling plugin suites with disposable profiles and local fixtures.

No dependency installation, network fixture downloads, or live profile copying.
External game/launcher operations must remain mocked by the tests themselves.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


CORE = Path(__file__).resolve().parents[1]


def isolated_environment(root, scale='1'):
    environment = os.environ.copy()
    # Do not allow inherited interpreter or desktop paths to escape the profile.
    for name in list(environment):
        if name.startswith(('PLAYLITE_', 'PYTHON')) or name in (
                'DBUS_SESSION_BUS_ADDRESS', 'DISPLAY', 'WAYLAND_DISPLAY', 'XAUTHORITY'):
            environment.pop(name)
    environment.update(HOME=str(root / 'home'), PLAYLITE_PROFILE='test',
                       PLAYLITE_HOST_HOME=str(root / 'host'),
                       QT_QPA_PLATFORM='offscreen', QT_SCALE_FACTOR=scale,
                       PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1',
                       PYTHONFAULTHANDLER='1',
                       PYTHONPATH=os.pathsep.join((str(CORE), str(CORE / 'tests'))),
                       XDG_RUNTIME_DIR=str(root / 'runtime'))
    for name in ('DATA', 'CONFIG', 'CACHE', 'STATE'):
        key = f'XDG_{name}_HOME'
        environment[key] = str(root / name.lower())
        environment['PLAYLITE_HOST_' + key] = str(root / 'host' / name.lower())
    for key, value in environment.items():
        if key in ('HOME', 'PLAYLITE_HOST_HOME', 'XDG_RUNTIME_DIR') or key.startswith(('XDG_', 'PLAYLITE_HOST_XDG_')) and key.endswith('_HOME'):
            Path(value).mkdir(parents=True, exist_ok=True, mode=0o700)
    return environment


def copy_plugin_fixtures(destination):
    for checkout in sorted(CORE.parent.glob('playlite-plugin-*')):
        if not (checkout / 'manifest.json').is_file():
            continue
        # Deliberately exclude untracked files, ignored credentials and artifacts.
        files = subprocess.check_output(['git', '-C', str(checkout), 'ls-files', '-z']).decode().split('\0')
        for name in filter(None, files):
            path = Path(name)
            if path.parts[0] in ('.github', 'tests'):
                continue
            source = checkout / path
            if source.is_symlink():
                raise ValueError(f'Test fixtures must not contain symlinks: {source}')
            if source.is_file():
                target = destination / checkout.name / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repositories', nargs='*', help='Directory names; defaults to core and all sibling plugins.')
    parser.add_argument('--pattern', default='test*.py')
    parser.add_argument('--match', help='Run only tests matching this unittest name pattern.')
    parser.add_argument('--scale', choices=('1', '1.5', '2'), default='1')
    parser.add_argument('--core-only', action='store_true', help='Do not provide plugin fixtures.')
    args = parser.parse_args(argv)
    repositories = {path.name: path for path in [CORE, *sorted(CORE.parent.glob('playlite-plugin-*'))]
                    if (path / 'tests').is_dir()}
    unknown = set(args.repositories) - repositories.keys()
    if unknown:
        parser.error('Unknown repositories: ' + ', '.join(sorted(unknown)))
    failures = []
    for name in args.repositories or repositories:
        with tempfile.TemporaryDirectory(prefix='playlite-tests-') as temporary:
            environment = isolated_environment(Path(temporary), args.scale)
            if not args.core_only:
                copy_plugin_fixtures(Path(environment['XDG_DATA_HOME']) / 'playlite/plugins')
            print(f'Checking {name} at scale {args.scale}', flush=True)
            try:
                command = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', args.pattern, '-q']
                if args.match:
                    command.extend(['-k', args.match])
                result = subprocess.run(command, cwd=repositories[name], env=environment,
                                        capture_output=True, text=True, timeout=180)
                output = result.stdout + result.stderr
                if result.returncode:
                    failures.append(name)
                    print(f'Process exited with status {result.returncode}.', flush=True)
                    print(output, flush=True)
                else:
                    print('\n'.join(line for line in output.splitlines()
                                    if line.startswith(('Ran ', 'OK'))), flush=True)
            except subprocess.TimeoutExpired:
                failures.append(name)
                print('Suite exceeded 180 seconds.', flush=True)
    print('Failed: ' + ', '.join(failures) if failures else 'All selected suites passed.')
    return bool(failures)


if __name__ == '__main__':
    sys.exit(main())
