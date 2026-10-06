"""Keep installed development plugins synchronized with sibling checkouts."""
import json
import os
from pathlib import Path
import subprocess
import threading
import tempfile


def sync_plugins(source, destination):
    for checkout in source.glob('playlite-plugin-*'):
        target = destination / checkout.name
        if not (target / 'manifest.json').is_file() or not (checkout / '.git').exists():
            continue
        files = subprocess.check_output(['git', '-C', str(checkout), 'ls-files', '-z']).decode().split('\0')
        for name in files:
            path = Path(name)
            if not name or path.parts[0] in ('.github', 'tests') or path.suffix in ('.md',):
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
