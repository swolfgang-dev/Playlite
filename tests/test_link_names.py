import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QLabel
from PyQt6.QtCore import QRect
from playlite.link_names import friendly_name, load_names, LinkNamesDialog
from playlite.settings import SettingsDialog

APP = QApplication.instance() or QApplication([])


class LinkNamesTests(unittest.TestCase):
    def test_game_name_variants_resolve_to_official_website(self):
        from playlite.link_names import DEFAULT_NAMES
        for url, name in [('https://shadowsoverloathing.com', 'Shadows Over Loathing'),
                          ('https://www.the-witcher-3.com', 'The Witcher 3'),
                          ('https://witcher3.com', 'The Witcher 3'),
                          ('https://developer.example/games/blasphemous-2', 'Blasphemous 2'),
                          ('https://pokemon.example', 'Pokémon')]:
            self.assertEqual(friendly_name(url, 'Original label', DEFAULT_NAMES, name), 'Official Website')
        self.assertEqual(friendly_name('https://store.steampowered.com/app/1/Blasphemous_2', '', DEFAULT_NAMES, 'Blasphemous 2'), 'Steam')
        self.assertEqual(friendly_name('https://unrelated.example', 'Custom label', DEFAULT_NAMES, 'Blasphemous 2'), 'Custom label')
        self.assertEqual(friendly_name('https://shadowsoverloathing.com', '', [('shadowsoverloathing.com', 'My label')], 'Shadows Over Loathing'), 'My label')

    def test_metadata_downloader_preserves_stored_link_names(self):
        from playlite.metadata_dialog import MetadataDownloader
        links = [{'Name': 'store.steampowered.com', 'Url': 'https://store.steampowered.com/app/42/'},
                 {'Name': '', 'Url': 'https://igdb.com/games/example'},
                 {'Name': 'My label', 'Url': 'https://example.com'}]
        current = {'Name': 'Example', 'Links': links}
        from unittest.mock import patch
        from playlite.providers import MetadataProvider
        provider = MetadataProvider()
        provider.id, provider.name = 'Test', 'Test'
        provider.fields = frozenset({'Links'})
        with patch('playlite.providers.discover_providers', return_value={'Test': provider}):
            dialog = MetadataDownloader(current, mode='metadata')
        self.assertEqual(dialog.current['Links'], links)
        self.assertEqual(current['Links'], links)
        dialog.reject()
        dialog.cache.cleanup()

    def test_link_flow_uses_rows_dots_and_wrapped_labels(self):
        from playlite.app import LinkLayout, LinkContent
        content = LinkContent()
        flow = LinkLayout()
        content.setLayout(flow)
        for name in ('Steam', 'IGDB', 'A long friendly website name'):
            label = QLabel(name)
            label.setWordWrap(True)
            flow.addWidget(label)
        flow.setGeometry(QRect(0, 0, 500, 200))
        self.assertEqual(len(flow.separators), 2)
        wide_height = flow.heightForWidth(500)
        flow.setGeometry(QRect(0, 0, 80, 400))
        self.assertGreater(flow.heightForWidth(80), wide_height)
        self.assertGreater(flow.items[-1].geometry().height(), flow.items[0].geometry().height())
        self.assertEqual(flow.separators, [])

    def test_domains_match_subdomains_with_specific_overrides(self):
        names = [('example.com', 'Example'), ('shop.example.com', 'Shop')]
        self.assertEqual(friendly_name('https://www.example.com/game', 'Original', names), 'Example')
        self.assertEqual(friendly_name('https://shop.example.com/game', 'Original', names), 'Shop')
        self.assertEqual(friendly_name('https://notexample.com', 'Original', names), 'Original')

    def test_manage_names_validates_duplicates_and_removal(self):
        dialog = LinkNamesDialog([])
        dialog.add_row('https://www.example.com/games', 'Example')
        dialog.add_row('example.com', 'Duplicate')
        dialog.save()
        self.assertIn('already listed', dialog.error.text())
        dialog.table.selectRow(1)
        dialog.remove_rows()
        dialog.save()
        self.assertEqual(dialog.names, [('example.com', 'Example')])

    def test_general_settings_save_cancel_and_empty_list(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'ui.ini'), QSettings.Format.IniFormat)
            initial = load_names(settings)
            dialog = SettingsDialog(settings)
            self.assertEqual(dialog.link_names_button.text(), 'Link names…')
            dialog.link_names = [('example.com', 'Example')]
            dialog.reject()
            self.assertEqual(load_names(settings), initial)
            dialog = SettingsDialog(settings)
            dialog.link_names = [('example.com', 'Example')]
            dialog.save()
            self.assertEqual(load_names(settings), [('example.com', 'Example')])
            dialog = SettingsDialog(settings)
            dialog.link_names = []
            dialog.save()
            self.assertEqual(load_names(settings), [])
