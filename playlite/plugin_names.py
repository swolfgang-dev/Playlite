"""Installed folder names for Playlite plugins."""
import re

PLUGIN_FOLDERS = {
    'GameArchiver': 'playlite-plugin-game-archiver',
    'IGDB': 'playlite-plugin-igdb',
    'ImageStudio': 'playlite-plugin-image-studio',
    'LutrisIntegration': 'playlite-plugin-lutris-integration',
    'SteamDepotDownloader': 'playlite-plugin-steam-depot-downloader',
    'SteamMetadata': 'playlite-plugin-steam-metadata',
    'SteamIntegration': 'playlite-plugin-steam-integration',
    'SteamAutoCrack': 'playlite-plugin-steamautocrack',
    'SteamGridDB': 'playlite-plugin-steamgriddb',
}


def plugin_folder(manifest):
    identity = manifest['id']
    if identity in PLUGIN_FOLDERS:
        return PLUGIN_FOLDERS[identity]
    repository = manifest.get('repository', '').split('/')[-1]
    if re.fullmatch(r'playlite-plugin-[a-zA-Z0-9_.-]+', repository):
        return repository
    return 'playlite-plugin-' + identity.lower()

