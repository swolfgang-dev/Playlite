import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import Mock, patch
from PyQt6.QtWidgets import QApplication
from playlite.steam_association import SteamAssociationDialog

APP = QApplication.instance() or QApplication([])


class SteamAssociationTests(unittest.TestCase):
    def setUp(self):
        patcher = patch('playlite.steam_association.installed_games', return_value=[{'app_id': '42', 'name': 'Installed game'}])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_local_selection_is_available_without_online_provider(self):
        dialog = SteamAssociationDialog()
        self.addCleanup(dialog.close)
        dialog.results.setCurrentRow(0)
        dialog.select()
        self.assertEqual(dialog.selected_game, {'id': '42', 'name': 'Installed game'})

    def test_online_search_supports_uninstalled_and_fuzzy_title_results(self):
        dialog = SteamAssociationDialog('UninstalledGame')
        self.addCleanup(dialog.close)
        provider = Mock(search=Mock(return_value=[{'id': 84, 'name': 'Uninstalled Game'}]))
        pool = Mock(start=lambda task: task.run())
        with patch('playlite.providers.discover_providers', return_value={'SteamMetadata': provider}), patch('playlite.steam_association.QThreadPool.globalInstance', return_value=pool):
            dialog.search()
        self.assertEqual(dialog.results.count(), 1)
        self.assertFalse(dialog.results.item(0).isHidden())
        dialog.results.setCurrentRow(0)
        dialog.select()
        self.assertEqual(dialog.selected_game['id'], '84')

    def test_online_errors_restore_controls(self):
        dialog = SteamAssociationDialog('Example')
        self.addCleanup(dialog.close)
        provider = Mock(search=Mock(side_effect=ValueError('Network unavailable')))
        with patch('playlite.providers.discover_providers', return_value={'SteamMetadata': provider}), patch('playlite.steam_association.QThreadPool.globalInstance', return_value=Mock(start=lambda task: task.run())):
            dialog.search()
        self.assertIn('Network unavailable', dialog.status.text())
        self.assertTrue(dialog.search_button.isEnabled())
        self.assertTrue(dialog.query.isEnabled())
        self.assertIsNone(dialog.task)

    def test_missing_provider_uses_core_steam_catalogue(self):
        dialog = SteamAssociationDialog('Example')
        self.addCleanup(dialog.close)
        with patch('playlite.providers.discover_providers', return_value={}), patch('playlite.steam_catalogue.search_games', return_value=[{'id':'84','name':'Example Game'}]) as search, patch('playlite.steam_association.QThreadPool.globalInstance', return_value=Mock(start=lambda task: task.run())):
            dialog.search()
        search.assert_called_once_with('Example')
        self.assertEqual(dialog.results.count(),1)
        self.assertTrue(dialog.search_button.isEnabled())
        dialog.results.setCurrentRow(0)
        dialog.select()
        self.assertEqual(dialog.selected_game['id'],'84')
