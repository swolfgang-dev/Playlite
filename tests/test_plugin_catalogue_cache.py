import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QApplication
from playlite.plugin_catalogue_cache import PluginCatalogueCache, catalogue_cache
from playlite.settings import SettingsDialog

APP = QApplication.instance() or QApplication([])
PLUGIN = dict(name='Example', version='v1', description='Example plugin', repository='owner/example')

class CatalogueCacheTests(unittest.TestCase):
    def test_available_shows_newer_versions_with_update_icon(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_DATA_HOME': directory}):
            cache = catalogue_cache()
            old = cache.plugins, cache.loaded, cache.loading, cache.error
            installed = dict(id='Example', name='Example', version='1.9', enabled=False,
                             repository='owner/source', distribution_repository='OWNER/EXAMPLE')
            try:
                cache.complete([dict(PLUGIN, version='v1.10')])
                with patch('playlite.plugin_manager.installed_plugins', return_value=[installed]):
                    dialog = SettingsDialog(QSettings(str(Path(directory) / 'ui.ini'), QSettings.Format.IniFormat))
                    self.assertEqual(dialog.available_plugins.rowCount(), 1)
                    name = dialog.available_plugins.item(0, 0)
                    self.assertFalse(name.icon().isNull())
                    installed_name = dialog.installed_plugins.item(0, 0)
                    self.assertFalse(installed_name.icon().isNull())
                    self.assertIn('Update available: 1.9 → v1.10', installed_name.toolTip())
                    self.assertIn('Update available', name.toolTip())
                    self.assertEqual(dialog.available_plugins.item(0, 1).text(), '1.9 → v1.10')
                    self.assertEqual(name.data(Qt.ItemDataRole.UserRole), 'owner/example')
                    for version in ('v1.9', 'v1.8'):
                        cache.complete([dict(PLUGIN, version=version)])
                        self.assertEqual(dialog.available_plugins.rowCount(), 0)
                        self.assertTrue(installed_name.icon().isNull())
                        self.assertNotIn('Update available:', installed_name.toolTip())
                    # Successful installation removes the entry on refresh.
                    cache.complete([dict(PLUGIN, version='v1.10')])
                    installed['version'] = '1.10'
                    dialog.refresh_installed_plugins()
                    self.assertEqual(dialog.available_plugins.rowCount(), 0)
                    self.assertTrue(dialog.installed_plugins.item(0, 0).icon().isNull())
                    dialog.reject()
            finally:
                cache.plugins, cache.loaded, cache.loading, cache.error = old

    def test_installed_plugins_hidden_and_reappear_after_deletion(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_DATA_HOME': directory}):
            cache = catalogue_cache()
            old = (cache.plugins, cache.loaded, cache.loading, cache.error)
            cache.complete([PLUGIN])
            installed = dict(id='Example', name='Example', version='1', enabled=False,
                             repository='owner/source', distribution_repository='owner/example')
            try:
                with patch('playlite.plugin_manager.installed_plugins', return_value=[installed]):
                    dialog = SettingsDialog(QSettings(str(Path(directory) / 'ui.ini'), QSettings.Format.IniFormat))
                    self.assertEqual(dialog.available_plugins.rowCount(), 0)
                    self.assertEqual(dialog.available_status.text(), '0 available plugins')
                with patch('playlite.plugin_manager.installed_plugins', return_value=[]):
                    dialog.refresh_installed_plugins()
                    self.assertEqual(dialog.available_plugins.rowCount(), 1)
                    self.assertEqual(dialog.available_status.text(), '1 available plugins')
                dialog.reject()
            finally:
                cache.plugins, cache.loaded, cache.loading, cache.error = old

    def test_refresh_coalesces_and_keeps_previous_list_on_error(self):
        cache = PluginCatalogueCache()
        pool = Mock()
        with patch('playlite.plugin_catalogue_cache.QThreadPool.globalInstance', return_value=pool), patch('playlite.plugin_catalogue_cache.available_plugins', return_value=[PLUGIN]) as fetch:
            cache.refresh()
            cache.refresh()
            pool.start.assert_called_once()
            cache.task.run()
            fetch.assert_called_once()
            self.assertEqual(cache.plugins, [PLUGIN])
            self.assertTrue(cache.loaded)
            self.assertFalse(cache.loading)
            cache.failed('offline')
            self.assertEqual(cache.plugins, [PLUGIN])
            self.assertEqual(cache.error, 'offline')

    def test_opening_and_switching_settings_uses_shared_snapshot(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_DATA_HOME': directory}):
            cache = catalogue_cache()
            old = (cache.plugins, cache.loaded, cache.loading, cache.error)
            cache.complete([PLUGIN])
            try:
                with patch.object(cache, 'refresh') as refresh:
                    for index in range(2):
                        dialog = SettingsDialog(QSettings(str(Path(directory)/f'{index}.ini'), QSettings.Format.IniFormat))
                        dialog.plugin_tabs.setCurrentIndex(1)
                        dialog.plugin_tabs.setCurrentIndex(0)
                        dialog.plugin_tabs.setCurrentIndex(1)
                        self.assertEqual(dialog.available_plugins.rowCount(), 1)
                        self.assertEqual(dialog.available_plugins.item(0,0).text(), 'Example')
                        self.assertEqual(refresh.call_count, index)
                        dialog.available_refresh_button.click()
                        self.assertEqual(refresh.call_count, index + 1)
                        dialog.reject()
            finally:
                cache.plugins, cache.loaded, cache.loading, cache.error = old

    def test_access_change_discards_an_inflight_authenticated_result(self):
        cache = PluginCatalogueCache()
        cache.loading = True
        cache.invalidate()
        with patch.object(cache, 'refresh') as refresh:
            cache.complete([PLUGIN])
            self.assertEqual(cache.plugins, [])
            self.assertFalse(cache.loaded)
            refresh.assert_called_once()
