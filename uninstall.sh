#!/usr/bin/env bash
set -euo pipefail
if [[ $# -eq 0 && -t 0 ]]; then
    read -r -p "Keep user settings for reinstalling? [Y/n] " playlite_keep_settings
    if [[ "$playlite_keep_settings" =~ ^[Nn]$ ]]; then
        set -- --remove-settings
    else
        set -- --keep-settings
    fi
    read -r -p "Keep installed plugins for reinstalling? [Y/n] " playlite_keep_plugins
    if [[ "$playlite_keep_plugins" =~ ^[Nn]$ ]]; then
        set -- "$@" --remove-plugins
    else
        set -- "$@" --keep-plugins
    fi
fi
exec python3 "$(dirname -- "${BASH_SOURCE[0]}")/uninstall.py" "$@"
