import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication
from playlite.providers import discover_plugins, installation_methods
from playlite.plugin_manager import install_archive, installed_plugins
from playlite.settings import SettingsDialog
from playlite.add_game import AddGameEditor

APP = QApplication.instance() or QApplication([])


class PluginInstallationTests(unittest.TestCase):
    def archive(self, root, enabled=True, version='1.0.0'):
        path = root / 'plugin.zip'
        manifest = dict(id='Example', name='Example plugin', type='generic', version=version, api_version=1, enabled=enabled)
        with ZipFile(path, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(manifest))
            archive.writestr('plugin.py', 'from playlite.providers import GenericPlugin\nclass Plugin(GenericPlugin):\n    pass\n')
        return path

    def test_manual_is_built_in_and_application_opens_without_plugins(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_DATA_HOME': directory}):
            self.assertEqual(discover_plugins(), {})
            self.assertEqual(set(installation_methods({})), {'Manual'})
            dialog = AddGameEditor(None, Path(directory))
            self.assertEqual(dialog.installation_method.currentData(), 'Manual')
            dialog.reject()
            settings = SettingsDialog(QSettings(str(Path(directory) / 'settings.ini'), QSettings.Format.IniFormat))
            self.assertEqual(settings.installed_plugins.rowCount(), 0)
            self.assertEqual(settings.plugin_widgets, {})
            settings.reject()

    def test_install_update_preserves_disabled_state_and_loads_plugin(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            plugins = root / 'plugins'
            install_archive(self.archive(root, enabled=False), plugins, 'owner/repo')
            result = install_archive(self.archive(root, version='2.0.0'), plugins, 'owner/repo')
            self.assertFalse(result['enabled'])
            self.assertEqual(result['version'], '2.0.0')
            self.assertEqual(discover_plugins(plugins), {})
            self.assertEqual(set(discover_plugins(plugins, include_disabled=True)), {'Example'})
            self.assertEqual(installed_plugins(plugins)[0]['repository'], 'owner/repo')

    def test_unsafe_archive_does_not_replace_installed_plugin(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            plugins = root / 'plugins'
            install_archive(self.archive(root), plugins)
            with ZipFile(root / 'unsafe.zip', 'w') as archive:
                archive.writestr('../outside.txt', 'bad')
            with self.assertRaises(ValueError):
                install_archive(root / 'unsafe.zip', plugins)
            self.assertFalse((root / 'outside.txt').exists())
            self.assertEqual(installed_plugins(plugins)[0]['version'], '1.0.0')

    def test_reserved_manual_plugin_is_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.archive(root)
            with ZipFile(path, 'w') as archive:
                archive.writestr('manifest.json', json.dumps(dict(id='Manual', name='Manual', version='1', api_version=1)))
                archive.writestr('plugin.py', 'pass')
            with self.assertRaises(ValueError):
                install_archive(path, root / 'plugins')

    def test_cleanup_survives_individual_plugin_removal(self):
        from playlite.plugin_manager import delete_plugin
        with TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'resource-plugin.zip'
            script = "def cleanup(*args):\n    pass\n"
            with ZipFile(archive, 'w') as bundle:
                bundle.writestr('manifest.json', json.dumps(dict(id='Example', name='Example', version='1',
                    api_version=1, type='generic', uninstall_hook='cleanup.py')))
                bundle.writestr('plugin.py', 'from playlite.providers import GenericPlugin\nclass Plugin(GenericPlugin):\n    pass\n')
                bundle.writestr('cleanup.py', script)
            plugins = root / 'plugins'
            install_archive(archive, plugins)
            registration = root / 'plugin-cleanup/Example'
            self.assertEqual((registration / 'cleanup.py').read_text(), script)
            entry = installed_plugins(plugins)[0]
            delete_plugin(entry['id'], plugins)
            self.assertFalse(Path(entry['manifest_path']).exists())
            self.assertEqual((registration / 'cleanup.py').read_text(), script)

    def test_repository_update_can_change_plugin_id_without_duplicate_folder(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            plugins = root / 'plugins'
            install_archive(self.archive(root, enabled=False), plugins, 'owner/playlite-plugin-example')
            archive = root / 'renamed.zip'
            with ZipFile(archive, 'w') as bundle:
                bundle.writestr('manifest.json', json.dumps(dict(id='Renamed', name='Renamed', version='2', api_version=1, type='generic')))
                bundle.writestr('plugin.py', 'from playlite.providers import GenericPlugin\nclass Plugin(GenericPlugin):\n    pass\n')
            install_archive(archive, plugins, 'owner/playlite-plugin-example')
            entries = installed_plugins(plugins)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]['id'], 'Renamed')
            self.assertFalse(entries[0]['enabled'])
