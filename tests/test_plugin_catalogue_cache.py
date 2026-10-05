import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication
from playlite.plugin_catalogue_cache import PluginCatalogueCache, catalogue_cache
from playlite.settings import SettingsDialog

APP = QApplication.instance() or QApplication([])
PLUGIN = dict(name='Example', version='v1', description='Example plugin', repository='owner/example')

class CatalogueCacheTests(unittest.TestCase):
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
