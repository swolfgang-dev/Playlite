"""Reset only settings explicitly declared by an installed plugin."""
import os
from pathlib import Path, PurePosixPath


def clear_plugin_settings(manifest):
    from PyQt6.QtCore import QSettings
    for name in manifest.get('settings_groups', []):
        if not isinstance(name, str) or not name or any(c in name for c in '/\\'):
            raise ValueError('Invalid plugin settings group.')
        settings = QSettings('Playlite', name)
        settings.clear()
        settings.sync()
        if settings.status() != settings.Status.NoError:
            raise OSError('Could not remove plugin settings.')
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    for name in manifest.get('settings_files', []):
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or not relative.parts or relative.parts[0] != 'playlite':
            raise ValueError('Plugin settings files must be scoped to the Playlite config folder.')
        path = config.joinpath(*relative.parts)
        if path.parent.resolve() != config.resolve() / 'playlite':
            raise ValueError('Plugin settings file is outside the config folder.')
        if path.is_file() or path.is_symlink():
            path.unlink()
