"""Keep installed development plugins synchronized with sibling checkouts."""
import json
import os
from pathlib import Path
import subprocess
import threading
import tempfile


def prepare_dependencies(destination):
    """Install declared plugin requirements into the private repo runtime."""
    import re
    import sys
    from importlib.metadata import version, PackageNotFoundError
    pending = set()
    # The desktop may have core dependencies installed only in its user site,
    # which the isolated development profile deliberately excludes.
    for name, requirement in [('PyQt6', 'PyQt6>=6.6,<7'), ('Pillow', 'Pillow>=10,<13')]:
        try:
            installed = tuple(map(int, version(name).split('.')))
            minimum, maximum = ((6, 6), (7,)) if name == 'PyQt6' else ((10,), (13,))
            if not minimum <= installed < maximum:
                pending.add(requirement)
        except (PackageNotFoundError, ValueError):
            pending.add(requirement)
    for path in destination.glob('*/manifest.json'):
        manifest = json.loads(path.read_text())
        if manifest.get('enabled') is False:
            continue
        for requirement in manifest.get('requirements') or []:
            match = re.fullmatch(r'([A-Za-z0-9_.-]+)(?:>=([0-9.]+))?', requirement)
            if not match:
                raise ValueError('Invalid plugin dependency: ' + str(requirement))
            try:
                installed = version(match.group(1))
                if not match.group(2) or tuple(map(int, installed.split('.'))) >= tuple(map(int, match.group(2).split('.'))):
                    continue
            except (PackageNotFoundError, ValueError):
                pass
            pending.add(requirement)
    if pending:
        if sys.prefix == sys.base_prefix:
            raise ValueError('Repo dependencies require a virtual environment. Use run-dev.sh.')
        from importlib.util import find_spec
        if find_spec('pip') is None:
            # Some distro Pythons omit ensurepip; bootstrap only this private venv.
            import urllib.request
            with tempfile.TemporaryDirectory(prefix='playlite-pip-') as temporary:
                script = Path(temporary) / 'get-pip.py'
                with urllib.request.urlopen('https://bootstrap.pypa.io/get-pip.py', timeout=60) as response:
                    script.write_bytes(response.read())
                subprocess.run([sys.executable, str(script)], check=True)
        subprocess.run([sys.executable, '-m', 'pip', 'install', *sorted(pending)], check=True)


def sync_plugins(source, destination):
    for checkout in source.glob('playlite-plugin-*'):
        target = destination / checkout.name
        if not (target / 'manifest.json').is_file() or not (checkout / '.git').exists():
            continue
        files = subprocess.check_output(['git', '-C', str(checkout), 'ls-files', '--cached', '--others', '--exclude-standard', '-z']).decode().split('\0')
        for name in files:
            path = Path(name)
            if not name or path.parts[0] in ('.github', 'tests', 'dist', 'build', '.venv') or '__pycache__' in path.parts or path.suffix == '.pyc':
                continue
            if path.suffix == '.md' and path.parts[0] != 'tools':
                continue
            original = checkout / path
            if not original.is_file():
                continue
            output = target / path
            content = original.read_bytes()
            if name == 'manifest.json':
                manifest = json.loads(content)
                existing = json.loads(output.read_text())
                if 'enabled' in existing:
                    manifest['enabled'] = existing['enabled']
                content = (json.dumps(manifest, indent=2) + '\n').encode()
            if output.is_file() and output.read_bytes() == content:
                continue
            output.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as temporary:
                temporary.write(content)
                staged = Path(temporary.name)
            staged.chmod(original.stat().st_mode & 0o777)
            staged.replace(output)


def start():
    if os.environ.get('PLAYLITE_PROFILE') != 'repo':
        return
    source = Path(__file__).resolve().parents[2]
    destination = Path(os.environ['XDG_DATA_HOME']) / 'playlite/plugins'
    sync_plugins(source, destination)
    def watch():
        import logging
        while True:
            threading.Event().wait(1)
            try:
                sync_plugins(source, destination)
            except (OSError, ValueError, subprocess.CalledProcessError):
                logging.exception('Could not synchronize development plugins')
    threading.Thread(target=watch, daemon=True, name='playlite-dev-plugins').start()


if __name__ == '__main__':
    if os.environ.get('PLAYLITE_PROFILE') != 'repo':
        raise SystemExit('Dependency preparation is only for the repo profile.')
    destination = Path(os.environ['XDG_DATA_HOME']) / 'playlite/plugins'
    sync_plugins(Path(__file__).resolve().parents[2], destination)
    prepare_dependencies(destination)
