"""Optional setup/removal interfaces run on the GUI thread."""
import importlib.util
import json
from pathlib import Path
import sys
import types
import uuid
from .plugin_manager import installed_plugins, plugin_directory


def load_plugin(identity):
    entry = next((entry for entry in installed_plugins() if entry['id'] == identity), None)
    if entry is None or not entry.get('installation_hooks', False): return None
    root = Path(entry['manifest_path']).parent
    if root.is_symlink() or root.resolve().parent != plugin_directory().resolve():
        raise ValueError('Plugin setup is outside the plugin directory.')
    from .plugin_manifest import validate_manifest
    manifest_path = root / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    validate_manifest(manifest)
    if manifest['id'] != identity:
        raise ValueError('Plugin setup identity changed.')
    namespace = sys.modules.setdefault('playlite_install_hooks', types.ModuleType('playlite_install_hooks'))
    namespace.__path__ = []
    name = 'playlite_install_hooks.plugin_' + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(name, root / 'plugin.py', submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        from .providers import instantiate_plugin
        return instantiate_plugin(module, manifest, manifest_path)
    except BaseException:
        for key in list(sys.modules):
            if key == name or key.startswith(name + '.'):
                del sys.modules[key]
        raise


def installed_setup(manifests, parent, log):
    for manifest in manifests:
        try:
            plugin = load_plugin(manifest['id'])
            if plugin and callable(getattr(plugin, 'post_install', None)):
                plugin.post_install(parent)
        except Exception as error:
            log('Plugin installed; additional setup needs attention: ' + str(error))


def prepare_removal(identities, parent, log):
    for identity in identities:
        try:
            plugin = load_plugin(identity)
            if plugin and callable(getattr(plugin, 'prepare_uninstall', None)):
                if plugin.prepare_uninstall(parent) is False:
                    return False
        except Exception as error:
            log('Could not prepare plugin removal: ' + str(error))
            return False
    return True
