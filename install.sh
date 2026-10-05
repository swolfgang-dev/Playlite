#!/usr/bin/env bash
set -euo pipefail
playlite_repo="${PLAYLITE_REPOSITORY:-swolfgang-dev/Playlite}"
playlite_version="${1:-latest}"
command -v python3 >/dev/null || { echo 'Python 3.10 or later is required.' >&2; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10 or later is required"'
playlite_download="$(mktemp -d)"
trap 'rm -rf "$playlite_download"' EXIT
python3 - "$playlite_repo" "$playlite_version" "$playlite_download" <<'PYDOWNLOAD'
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import quote, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

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
    if token:
        headers['Authorization'] = 'Bearer ' + token
    with opener.open(Request(url, headers=headers), timeout=60) as response:
        return response.read()
release = 'latest' if version == 'latest' else 'tags/' + quote(version, safe='')
try:
    document = json.loads(fetch('https://api.github.com/repos/' + repository + '/releases/' + release))
    assets = document['assets']
    wheels = [asset for asset in assets if re.fullmatch(r'playlite-[A-Za-z0-9_.+-]+\.whl', asset['name'])]
    if len(wheels) != 1:
        raise ValueError('Expected one Playlite wheel.')
    selected = wheels + [next(asset for asset in assets if asset['name'] == name) for name in ('pip.pyz', 'SHA256SUMS')]
    for asset in selected:
        (Path(destination) / asset['name']).write_bytes(fetch(asset['url'], binary=True))
except Exception as error:
    raise SystemExit('Could not download the Playlite release: ' + str(error))
PYDOWNLOAD
python3 - "$playlite_download" <<'PY'
import hashlib
from pathlib import Path
import sys
root = Path(sys.argv[1])
checksums = {line.split()[-1].lstrip('*'): line.split()[0] for line in (root / 'SHA256SUMS').read_text().splitlines()}
wheels = list(root.glob('playlite-*.whl'))
assert len(wheels) == 1, 'Expected one Playlite wheel'
for wheel in [*wheels, root / 'pip.pyz']:
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == checksums[wheel.name], 'Wheel checksum mismatch'
PY
playlite_install_root="${XDG_DATA_HOME:-$HOME/.local/share}/playlite"
python3 -m venv --without-pip "$playlite_install_root/runtime"
"$playlite_install_root/runtime/bin/python" "$playlite_download/pip.pyz" install --upgrade pip "$playlite_download"/playlite-*.whl
playlite_bin="${PLAYLITE_BIN_DIR:-$HOME/.local/bin}"
mkdir -p "$playlite_bin"
for playlite_command in playlite playlite-cli playlite-plugins; do
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
echo 'Playlite installed. Launch it from your applications menu or run playlite.'
echo 'Optional plugins: Settings → Plugins → Available.'
