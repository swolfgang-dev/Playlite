"""Public release checks and an updater that runs outside the replaced runtime."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
from urllib.error import HTTPError
from urllib.parse import urlparse, unquote, quote
import re

REPOSITORY = 'swolfgang-dev/Playlite'


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Playlite-Updater', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def latest_release():
    try:
        release = json.loads(fetch(f'https://api.github.com/repos/{REPOSITORY}/releases/latest'))
    except HTTPError as error:
        if error.code not in (403,429):raise
        request=urllib.request.Request(f'https://github.com/{REPOSITORY}/releases/latest',headers={'User-Agent':'Playlite-Updater'})
        with urllib.request.urlopen(request,timeout=30) as response:
            path=urlparse(response.geturl()).path
        prefix=f'/{REPOSITORY}/releases/tag/'
        if not path.startswith(prefix):raise ValueError('Could not resolve the latest stable release.')
        tag=unquote(path[len(prefix):])
        if not re.fullmatch(r'v[0-9]+(?:\.[0-9]+)*',tag):raise ValueError('Invalid stable release tag.')
        base=f'https://github.com/{REPOSITORY}/releases/download/{quote(tag,safe="")}/'
        names=[line.split()[-1].lstrip('*') for line in fetch(base+'SHA256SUMS').decode().splitlines() if len(line.split())==2]
        release={'tag_name':tag,'assets':[{'name':name,'browser_download_url':base+name} for name in names
                 if re.fullmatch(r'[A-Za-z0-9_.+-]+',name)]}
        release['assets'].append({'name':'SHA256SUMS','browser_download_url':base+'SHA256SUMS'})
    if release.get('draft') or release.get('prerelease'):
        raise ValueError('No stable release is available.')
    return release


def prepare_update(release):
    import tempfile
    if os.environ.get('PLAYLITE_PROFILE') == 'repo':
        raise ValueError('Update the repo checkout through Git; this updater is for installed Playlite.')
    assets = {asset['name']: asset['browser_download_url'] for asset in release['assets']}
    checksums = fetch(assets['SHA256SUMS']).decode()
    hashes = {line.split()[-1].lstrip('*'): line.split()[0] for line in checksums.splitlines() if len(line.split()) == 2}
    script = fetch(assets['install.sh'])
    if hashlib.sha256(script).hexdigest() != hashes.get('install.sh'):
        raise ValueError('Installer checksum mismatch.')
    directory = Path(tempfile.mkdtemp(prefix='playlite-update-'))
    directory.chmod(0o700)
    (directory / 'install.sh').write_bytes(script)
    # Copy the helper before the installer replaces the current runtime.
    (directory / 'updater.py').write_bytes(Path(__file__).read_bytes())
    return directory


def launch_update(directory, tag):
    data = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'playlite'
    data.mkdir(parents=True, exist_ok=True)
    log = data / 'update.log'
    with log.open('w') as output:
        log.chmod(0o600)
        subprocess.Popen(['/usr/bin/python3', str(directory / 'updater.py'), str(os.getpid()), tag],
                         stdout=output, stderr=output, start_new_session=True)
    return log


def run_update(pid, tag):
    directory = Path(__file__).parent
    try:
        deadline = time.monotonic() + 300
        while Path(f'/proc/{pid}').exists():
            if time.monotonic() >= deadline:
                raise RuntimeError('Update cancelled: Playlite did not close within five minutes.')
            time.sleep(.25)
        result = subprocess.run(['bash', str(directory / 'install.sh'), tag, '--no-gui'])
        if result.returncode:
            raise RuntimeError('Update failed. The existing installer preserves or restores the previous runtime.')
        binary = Path(os.environ.get('PLAYLITE_BIN_DIR', str(Path.home() / '.local/bin'))) / 'playlite'
        subprocess.Popen([str(binary)], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        import shutil
        shutil.rmtree(directory)


if __name__ == '__main__':
    run_update(int(sys.argv[1]), sys.argv[2])
