"""Known plugin settings, separate from external application libraries."""
from pathlib import Path

SETTINGS = {
    'LutrisIntegration': 'Lutris', 'SteamIntegration': 'Steam',
    'SteamDepotDownloader': 'SteamDownloader', 'SteamAutoCrack': 'SteamAutoCrack',
    'GameArchiver': 'Archiver',
}


def clear_plugin_settings(identity):
    from PyQt6.QtCore import QSettings
    name = SETTINGS.get(identity)
    if name:
        settings = QSettings('Playlite', name)
        settings.clear()
        settings.sync()
        if settings.status() != settings.Status.NoError:
            raise OSError('Could not remove settings for ' + identity)
    if identity == 'IGDB':
        path = Path.home() / '.config/playlite/igdb.json'
        if path.is_file() or path.is_symlink():
            path.unlink()
