"""Installed folder names for Playlite plugins."""
import re



def plugin_folder(manifest):
    identity = manifest['id']
    repository = manifest.get('repository', '').split('/')[-1]
    if re.fullmatch(r'playlite-plugin-[a-zA-Z0-9_.-]+', repository):
        return repository
    return 'playlite-plugin-' + identity.lower()

