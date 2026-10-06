#!/usr/bin/env bash
# Private development profile: never read the release installation's user files.
set -euo pipefail
playlite_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PLAYLITE_PROFILE=repo
export HOME="$playlite_source/.dev/home"
export XDG_DATA_HOME="$HOME/.local/share"
export XDG_CONFIG_HOME="$HOME/.config"
export XDG_CACHE_HOME="$HOME/.cache"
export XDG_STATE_HOME="$HOME/.local/state"
export PYTHONNOUSERSITE=1
unset PYTHONPATH PYTHONHOME
mkdir -p "$HOME" "$XDG_DATA_HOME" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_STATE_HOME"
chmod 700 "$HOME"
cd "$playlite_source"
exec /usr/bin/python3 -m playlite "$@"
