import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from playlite.app import LibraryWindow
from playlite.library import query_games, filter_values
from playlite.library_filters import LibraryFilter

APP = QApplication.instance() or QApplication([])


class LibraryFilterTests(unittest.TestCase):
    def test_multiple_values_are_or_within_a_filter_and_and_across_filters(self):
        games = [dict(Id='a', Name='A', Genres=['RPG'], PlayActions=[dict(Integration='SteamIntegration')]),
                 dict(Id='b', Name='B', Genres=['Action'], PlayActions=[dict(Integration='SteamIntegration')]),
                 dict(Id='c', Name='C', Genres=['Action'], PlayActions=[dict(Integration='LutrisIntegration')])]
        filtered = query_games(games, filters={'Genres': ['RPG', 'Action'], 'Source': ['SteamIntegration']})
        self.assertEqual([g['Id'] for g in filtered], ['a', 'b'])

    def test_sources_use_all_actions_and_ignore_stale_source_metadata(self):
        games = [dict(Id='a', Name='Both', Source='Old', PlayActions=[
                    dict(Integration='SteamIntegration'), dict(Integration='LutrisIntegration'),
                    dict(Integration='LutrisIntegration')]),
                 dict(Id='b', Name='No actions', Source='Steam', PlayActions=[]),
                 dict(Id='c', Name='Legacy', GameProvider='LutrisIntegration'),
                 dict(Id='d', Name='Removed', GameProvider='LutrisIntegration', PlayActions=[])]
        self.assertEqual(filter_values(games[0], 'Source'), ['SteamIntegration', 'LutrisIntegration'])
        self.assertEqual([g['Id'] for g in query_games(games, filters={'Source': ['LutrisIntegration']})], ['a', 'c'])
        self.assertEqual([g['Id'] for g in query_games(games, filters={'Source': [None]})], ['b', 'd'])

    def test_sources_dropdown_has_friendly_labels_and_filters_by_action(self):
        with TemporaryDirectory() as directory:
            data = Path(directory)
            (data / 'library.json').write_text(json.dumps([
                dict(Id='a', Name='Both', PlayActions=[dict(Integration='SteamIntegration'), dict(Integration='LutrisIntegration')]),
                dict(Id='b', Name='Steam', PlayActions=[dict(Integration='SteamIntegration')]),
                dict(Id='c', Name='None', Source='Steam', PlayActions=[])]))
            window = LibraryWindow(data)
            try:
                source = window.filter_controls['Source']
                self.assertIn(('Lutris', 'LutrisIntegration'), source.options)
                self.assertIn(('Steam', 'SteamIntegration'), source.options)
                source.set_values(['LutrisIntegration'])
                self.assertEqual(window.list.count(), 1)
                self.assertEqual(window.current['Id'], 'a')
                source.set_values([None])
                self.assertEqual(window.current['Id'], 'c')
            finally:
                window.close()

    def test_none_matches_missing_null_empty_and_empty_date_metadata(self):
        games = [dict(Id='a', Name='A'), dict(Id='b', Name='B', Genres=None),
                 dict(Id='c', Name='C', Genres=[]), dict(Id='d', Name='D', Genres=['RPG']),
                 dict(Id='e', Name='E', Genres=[''], ReleaseDate={'ReleaseDate': None})]
        self.assertEqual([g['Id'] for g in query_games(games, filters={'Genres': [None]})], ['a', 'b', 'c', 'e'])
        self.assertEqual(len(query_games(games, filters={'Genres': [None, 'RPG']})), 5)
        self.assertEqual(len(query_games(games, filters={'ReleaseDate': [None]})), 5)
        self.assertEqual(len(query_games(games, filters={'Platforms': [None]})), 5)

    def test_installation_states_support_multiple_choices(self):
        games = [dict(Id='a', Name='A', IsInstalled=True), dict(Id='b', Name='B')]
        self.assertEqual([g['Id'] for g in query_games(games, filters={'Installed': ['Not installed']})], ['b'])
        self.assertEqual(len(query_games(games, filters={'Installed': ['Installed', 'Not installed']})), 2)

    def test_checkbox_clicks_keep_dropdown_open_and_all_clears_selection(self):
        control = LibraryFilter('Completion statuses', [('None', None), ('Playing', 'Playing'), ('Completed', 'Completed')])
        control.show()
        control.menu().popup(control.mapToGlobal(QPoint(0, control.height())))
        APP.processEvents()
        try:
            self.assertEqual(control.text(), 'All completion statuses')
            QTest.mouseClick(control.boxes[None], Qt.MouseButton.LeftButton)
            QTest.mouseClick(control.boxes['Playing'], Qt.MouseButton.LeftButton)
            self.assertEqual(control.values(), [None, 'Playing'])
            self.assertTrue(control.menu().isVisible())
            QTest.mouseClick(control.all, Qt.MouseButton.LeftButton)
            self.assertEqual(control.values(), [])
            self.assertEqual(control.text(), 'All completion statuses')
        finally:
            control.menu().close()
            control.close()

    def test_refresh_preserves_choices_and_migrates_legacy_single_selection(self):
        control = LibraryFilter('Genres', [('None', None), ('RPG', 'RPG')], 'RPG')
        self.assertEqual(control.values(), ['RPG'])
        control.set_values([None, 'RPG'])
        control.set_options([('None', None), ('Action', 'Action'), ('RPG', 'RPG')], control.values())
        self.assertEqual(control.values(), [None, 'RPG'])
        control.close()

    def test_window_persists_none_and_multiselect_and_clear_filters(self):
        with TemporaryDirectory() as directory:
            data = Path(directory)
            (data / 'library.json').write_text(json.dumps([
                dict(Id='a', Name='A', Genres=['RPG']), dict(Id='b', Name='B'),
                dict(Id='c', Name='C', Genres=['Action'])]))
            window = LibraryWindow(data)
            try:
                window.filter_controls['Genres'].set_values([None, 'RPG'])
                self.assertEqual(window.list.count(), 2)
                window.update_filter_choices()
                self.assertEqual(window.filter_controls['Genres'].values(), [None, 'RPG'])
            finally:
                window.close()
            reopened = LibraryWindow(data)
            try:
                self.assertEqual(reopened.filter_controls['Genres'].values(), [None, 'RPG'])
                self.assertEqual(reopened.list.count(), 2)
                reopened.apply_metadata_filter('Genres', 'Action')
                self.assertEqual(reopened.filter_controls['Genres'].values(), ['Action'])
                self.assertEqual(reopened.list.count(), 1)
                reopened.reset_filters()
                self.assertEqual(reopened.list.count(), 3)
                self.assertFalse(any(reopened.active_filters.values()))
            finally:
                reopened.close()
