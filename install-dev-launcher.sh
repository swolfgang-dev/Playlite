#!/usr/bin/env bash
set -euo pipefail
playlite_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
playlite_bin="${PLAYLITE_BIN_DIR:-$HOME/.local/bin}"
playlite_desktop="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$playlite_bin" "$playlite_desktop"
ln -sfn "$playlite_source/run-dev.sh" "$playlite_bin/playlite-dev"
cat > "$playlite_desktop/playlite-dev.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Playlite (Repo)
Comment=Isolated development version of Playlite
Exec="$playlite_source/run-dev.sh"
Icon=$playlite_source/playlite/assets/playlite.png
Terminal=false
Categories=Game;
EOF
echo 'Repo launcher installed: playlite-dev / Playlite (Repo).'
