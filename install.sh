#!/usr/bin/env bash
set -euo pipefail
if [[ "${PLAYLITE_PROFILE:-}" == repo ]]; then
    echo 'Run the release installer from a normal terminal, outside the repo profile.' >&2
    exit 1
fi
playlite_repo="${PLAYLITE_REPOSITORY:-swolfgang-dev/Playlite}"
playlite_version=latest
playlite_gui=no
playlite_release_directory=''
while [[ $# -gt 0 ]]; do
    playlite_argument="$1"
    shift
    case "$playlite_argument" in
        --gui) playlite_gui=yes ;;
        --no-gui) playlite_gui=no ;;
        --release-dir)
            [[ $# -gt 0 ]] || { echo '--release-dir requires a directory.' >&2; exit 1; }
            playlite_release_directory="$1"
            shift ;;
        --*) echo "Unknown option: $playlite_argument" >&2; exit 1 ;;
        *) playlite_version="$playlite_argument" ;;
    esac
done
command -v python3 >/dev/null || { echo 'Python 3.10 or later is required.' >&2; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10 or later is required"'
playlite_install_root="${XDG_DATA_HOME:-$HOME/.local/share}/playlite"
mkdir -p "$playlite_install_root"
command -v flock >/dev/null || { echo 'flock is required to serialize updates.' >&2; exit 1; }
exec 9>"$playlite_install_root/.install.lock"
flock -n 9 || { echo 'Another Playlite installation or update is running.' >&2; exit 1; }
[[ ! -L "$playlite_install_root/runtime" ]] || { echo 'Refusing to replace a symlinked runtime.' >&2; exit 1; }
python3 - "$playlite_install_root/runtime" <<'PYCLOSED'
import os
from pathlib import Path
import sys
runtime = str(Path(sys.argv[1]).absolute()) + '/bin/'
for process in Path('/proc').iterdir():
    try:
        if not process.name.isdecimal() or process.stat().st_uid != os.getuid(): continue
        arguments = (process / 'cmdline').read_bytes().split(b'\0')
        if any(argument.decode(errors='replace').startswith(runtime) for argument in arguments):
            raise SystemExit('Close the installed version of Playlite before updating. The repo version may stay open.')
    except OSError:
        pass
PYCLOSED
playlite_download="$(mktemp -d)"
playlite_stage=''
playlite_backup=''
playlite_switched=0
playlite_cleanup() {
    playlite_result=$?
    if [[ "$playlite_switched" == 1 ]]; then
        rm -rf -- "$playlite_install_root/runtime"
        if [[ -n "$playlite_backup" && -d "$playlite_backup/runtime" ]]; then
            mv -- "$playlite_backup/runtime" "$playlite_install_root/runtime" || {
                echo "Rollback failed. Previous runtime retained at $playlite_backup/runtime" >&2
                exit 1
            }
        fi
        echo 'Installation failed; the previous runtime was restored.' >&2
    fi
    [[ -z "$playlite_stage" ]] || rm -rf -- "$playlite_stage"
    [[ -z "$playlite_backup" ]] || rmdir -- "$playlite_backup" 2>/dev/null || true
    rm -rf -- "$playlite_download"
    exit "$playlite_result"
}
trap playlite_cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if [[ -n "$playlite_release_directory" ]]; then
    python3 - "$playlite_release_directory" "$playlite_download" <<'PYLOCAL'
from pathlib import Path
import shutil
import sys
source, destination = map(Path, sys.argv[1:])
wheels = list(source.glob('playlite-*.whl'))
if len(wheels) != 1:
    raise SystemExit('A local release must contain exactly one Playlite wheel.')
assets = wheels + [source / name for name in ('pip.pyz', 'SHA256SUMS', 'uninstall.sh', 'uninstall.py')]
for asset in assets:
    if not asset.is_file():
        raise SystemExit('Missing local release asset: ' + asset.name)
    shutil.copy2(asset, destination / asset.name)
PYLOCAL
else
python3 - "$playlite_repo" "$playlite_version" "$playlite_download" <<'PYDOWNLOAD'
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote, urlparse, unquote
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError

repository, version, destination = sys.argv[1:]
if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
    raise SystemExit('Invalid release repository.')
token = os.environ.get('PLAYLITE_GITHUB_TOKEN', '')
class Redirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, target):
        redirected = super().redirect_request(request, response, code, message, headers, target)
        if redirected is not None and urlparse(target).hostname != 'api.github.com':
            redirected.remove_header('Authorization')
        return redirected
opener = build_opener(Redirect())
def fetch(url, binary=False):
    headers = {'User-Agent': 'Playlite Installer', 'Accept': 'application/octet-stream' if binary else 'application/vnd.github+json'}
    if token and urlparse(url).hostname=='api.github.com':
        headers['Authorization'] = 'Bearer ' + token
    with opener.open(Request(url, headers=headers), timeout=60) as response:
        return response.read()
release = 'latest' if version == 'latest' else 'tags/' + quote(version, safe='')
try:
    try:
        document = json.loads(fetch('https://api.github.com/repos/' + repository + '/releases/' + release))
    except HTTPError as error:
        if error.code not in (403,429):raise
        tag=version
        if tag=='latest':
            with opener.open(Request('https://github.com/'+repository+'/releases/latest',headers={'User-Agent':'Playlite Installer'}),timeout=60) as response:
                path=urlparse(response.geturl()).path
            prefix='/'+repository+'/releases/tag/'
            if not path.startswith(prefix):raise ValueError('Could not resolve the latest release.')
            tag=unquote(path[len(prefix):])
        if not re.fullmatch(r'v[0-9]+(?:\.[0-9]+)*',tag):raise ValueError('Invalid stable release tag.')
        base='https://github.com/'+repository+'/releases/download/'+quote(tag,safe='')+'/'
        names=[line.split()[-1].lstrip('*') for line in fetch(base+'SHA256SUMS').decode().splitlines() if len(line.split())==2]
        document={'assets':[{'name':name,'browser_download_url':base+name} for name in names if re.fullmatch(r'[A-Za-z0-9_.+-]+',name)]}
        document['assets'].append({'name':'SHA256SUMS','browser_download_url':base+'SHA256SUMS'})
    assets = document['assets']
    wheels = [asset for asset in assets if re.fullmatch(r'playlite-[A-Za-z0-9_.+-]+\.whl', asset['name'])]
    if len(wheels) != 1:
        raise ValueError('Expected one Playlite wheel.')
    selected = wheels + [next(asset for asset in assets if asset['name'] == name) for name in ('pip.pyz', 'SHA256SUMS')]
    selected += [asset for asset in assets if asset['name'] in ('uninstall.sh', 'uninstall.py')]
    for asset in selected:
        (Path(destination) / asset['name']).write_bytes(fetch(asset['browser_download_url'], binary=True))
except Exception as error:
    raise SystemExit('Could not download the Playlite release: ' + str(error))
PYDOWNLOAD
fi
python3 - "$playlite_download" <<'PY'
import hashlib
from pathlib import Path
import sys
root = Path(sys.argv[1])
checksums = {line.split()[-1].lstrip('*'): line.split()[0] for line in (root / 'SHA256SUMS').read_text().splitlines()}
wheels = list(root.glob('playlite-*.whl'))
assert len(wheels) == 1, 'Expected one Playlite wheel'
for wheel in [*wheels, root / 'pip.pyz', *root.glob('uninstall.*')]:
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == checksums[wheel.name], 'Wheel checksum mismatch'
PY
playlite_stage="$(mktemp -d "$playlite_install_root/runtime.new.XXXXXXXX")"
python3 -m venv --without-pip "$playlite_stage"
"$playlite_stage/bin/python" "$playlite_download/pip.pyz" install --upgrade pip "$playlite_download"/playlite-*.whl
"$playlite_stage/bin/python" -I - "$playlite_download/pip.pyz" "$playlite_install_root/plugins" <<'PYPLUGINDEPS'
import json
from pathlib import Path
import re
import subprocess
import sys
requirements = set()
for manifest in Path(sys.argv[2]).glob('*/manifest.json'):
    values = json.loads(manifest.read_text()).get('requirements') or []
    if not isinstance(values, list) or any(not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+(?:>=[0-9.]+)?', value) for value in values):
        raise SystemExit('Invalid dependency requirements in ' + str(manifest))
    requirements.update(values)
if requirements:
    subprocess.run([sys.executable, '-I', sys.argv[1], 'install', *sorted(requirements)], check=True)
PYPLUGINDEPS
"$playlite_stage/bin/python" "$playlite_download/pip.pyz" check
playlite_verify() {
    "$1/bin/python" -I - "$1" <<'PYVERIFY'
from pathlib import Path
import sys
import playlite.app
import playlite.cli
import playlite.plugin_manager
from PyQt6 import QtWidgets
from PIL import Image
root = Path(sys.argv[1]).resolve()
assert Path(playlite.app.__file__).resolve().is_relative_to(root), 'Playlite loaded outside the new runtime'
assert (Path(playlite.app.__file__).parent / 'assets/playlite.png').is_file(), 'Application icon missing'
for name in ('playlite', 'playlite-cli', 'playlite-plugins', 'playlite-installer'):
    path = root / 'bin' / name
    assert path.is_file() and path.stat().st_mode & 0o111, 'Missing executable: ' + name
PYVERIFY
}
playlite_verify "$playlite_stage"
# Virtualenv console scripts embed absolute paths. Relocate those paths before
# switching directories; otherwise the new launchers point at deleted staging.
python3 - "$playlite_stage" "$playlite_install_root/runtime" <<'PYRELOCATE'
from pathlib import Path
import sys
stage, destination = map(Path, sys.argv[1:])
for path in [*(stage / 'bin').iterdir(), stage / 'pyvenv.cfg']:
    if path.is_symlink() or not path.is_file(): continue
    data = path.read_bytes()
    if b'\0' not in data and str(stage).encode() in data:
        path.write_bytes(data.replace(str(stage).encode(), str(destination).encode()))
PYRELOCATE
playlite_backup="$(mktemp -d "$playlite_install_root/runtime.old.XXXXXXXX")"
if [[ -d "$playlite_install_root/runtime" ]]; then
    mv -- "$playlite_install_root/runtime" "$playlite_backup/runtime"
fi
playlite_switched=1
mv -- "$playlite_stage" "$playlite_install_root/runtime"
playlite_stage=''
playlite_verify "$playlite_install_root/runtime"
"$playlite_install_root/runtime/bin/python" -I - <<'PYRECEIPT'
import sys
try:
    from playlite.ownership import record_tree
except ModuleNotFoundError as error:
    if error.name != 'playlite.ownership': raise
    # Older wheels predate receipts; this is still a freshly built environment.
    import hashlib
    import json
    import os
    from pathlib import Path
    def record_tree(root):
        root = Path(root)
        files = {}
        directories = []
        for directory, folders, names in os.walk(root, followlinks=False):
            directories.extend((Path(directory) / name).relative_to(root).as_posix() for name in folders if not (Path(directory) / name).is_symlink())
            for name in names + [name for name in folders if (Path(directory) / name).is_symlink()]:
                path = Path(directory) / name
                relative = path.relative_to(root).as_posix()
                if relative == '.playlite-owned.json': continue
                if path.is_symlink(): value = {'link': os.readlink(path)}
                else:
                    digest = hashlib.sha256()
                    with path.open('rb') as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b''): digest.update(chunk)
                    value = {'sha256': digest.hexdigest()}
                files[relative] = value
        (root / '.playlite-owned.json').write_text(json.dumps({'schema': 1, 'root': str(root.resolve()), 'files': files, 'directories': directories}))
        (root / '.playlite-owned.json').chmod(0o600)
record_tree(sys.prefix)
PYRECEIPT
playlite_bin="${PLAYLITE_BIN_DIR:-$HOME/.local/bin}"
mkdir -p "$playlite_bin"
for playlite_command in playlite playlite-cli playlite-plugins playlite-installer; do
    if [[ -f "$playlite_bin/$playlite_command" && ! -L "$playlite_bin/$playlite_command" ]]; then
        cp -n "$playlite_bin/$playlite_command" "$playlite_bin/$playlite_command.before-github-install"
    fi
    ln -sfn "$playlite_install_root/runtime/bin/$playlite_command" "$playlite_bin/$playlite_command"
done
playlite_desktop="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$playlite_desktop"
playlite_icon="$("$playlite_install_root/runtime/bin/python" -c 'from pathlib import Path; import playlite; print(Path(playlite.__file__).parent / "assets/playlite.png")')"
cat > "$playlite_desktop/playlite.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Playlite
Comment=Native Linux game library
Exec="$playlite_install_root/runtime/bin/playlite"
Icon=$playlite_icon
Terminal=false
Categories=Game;
EOF
if [[ -f "$playlite_download/uninstall.sh" && -f "$playlite_download/uninstall.py" ]]; then
    "$playlite_install_root/runtime/bin/python" -I - "$playlite_install_root" "$playlite_download" <<'PYSCRIPTS'
from pathlib import Path
import hashlib
import json
import shutil
import sys
root = Path(sys.argv[1])
source = Path(sys.argv[2])
marker = root / '.playlite-install-scripts.json'
previous = json.loads(marker.read_text()) if marker.is_file() and not marker.is_symlink() else {}
owned = previous.get('files', {}) if previous.get('root') == str(root.resolve()) else {}
for name in ('uninstall.sh', 'uninstall.py'):
    path = root / name
    if path.is_symlink() or (path.exists() and (not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != owned.get(name))):
        print('Existing manual uninstaller files retained. Use the release download for uninstall scripts.')
        raise SystemExit(0)
for name in ('uninstall.sh', 'uninstall.py'):
    shutil.copy2(source / name, root / name)
(root / 'uninstall.sh').chmod(0o755)
files = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ('uninstall.sh', 'uninstall.py')}
marker.write_text(json.dumps({'root': str(root.resolve()), 'files': files}))
PYSCRIPTS
fi
playlite_switched=0
rm -rf -- "$playlite_backup"
playlite_backup=''
echo 'Playlite installed. Launch it from your applications menu or run playlite.'
echo 'On first launch, Get started helps you choose preferences and install optional plugins.'
if [[ "$playlite_gui" == yes ]]; then
    "$playlite_install_root/runtime/bin/playlite" &
fi
