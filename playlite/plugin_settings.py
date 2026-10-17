"""Reset only settings explicitly declared by an installed plugin."""
import os
from pathlib import Path, PurePosixPath


def settings_targets(manifest):
    """Validate the complete reset request before removing any settings."""
    groups = manifest.get('settings_groups', [])
    files = manifest.get('settings_files', [])
    if not isinstance(groups, list) or not isinstance(files, list):
        raise ValueError('Plugin settings declarations must be lists.')
    for name in groups:
        if not isinstance(name, str) or not name or any(c in name for c in '/\\'):
            raise ValueError('Invalid plugin settings group.')
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    paths = []
    for name in files:
        if not isinstance(name, str) or '\\' in name or '\0' in name:
            raise ValueError('Invalid plugin settings file.')
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or not relative.parts or relative.parts[0] != 'playlite':
            raise ValueError('Plugin settings files must be scoped to the Playlite config folder.')
        path = config.joinpath(*relative.parts)
        if path.parent.resolve() != config.resolve() / 'playlite':
            raise ValueError('Plugin settings file is outside the config folder.')
        paths.append(path)
    return groups, paths


def clear_plugin_settings(manifest):
    from PyQt6.QtCore import QSettings
    groups, paths = settings_targets(manifest)
    for name in groups:
        settings = QSettings('Playlite', name)
        settings.clear()
        settings.sync()
        if settings.status() != settings.Status.NoError:
            raise OSError('Could not remove plugin settings.')
    for path in paths:
        if path.is_file() or path.is_symlink():
            path.unlink()
