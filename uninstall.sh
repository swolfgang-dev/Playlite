#!/usr/bin/env bash
set -euo pipefail
if [[ $# -eq 0 && -t 0 ]]; then
    read -r -p "Keep user settings for reinstalling? [Y/n] " playlite_keep_settings
    if [[ "$playlite_keep_settings" =~ ^[Nn]$ ]]; then
        set -- --remove-settings
    else
        set -- --keep-settings
    fi
fi
exec python3 "$(dirname -- "${BASH_SOURCE[0]}")/uninstall.py" "$@"
