import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock
import unittest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from playlite.providers import MetadataProvider
from playlite.metadata_dialog import MetadataDownloader

APP = QApplication.instance() or QApplication([])


class MetadataDefaultsTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_path = Path(self.directory.name) / 'ui.ini'
        providers = {}
        for identity, fields in [('First', {'Name', 'Description'}), ('Second', {'Name', 'Links'})]:
            provider = MetadataProvider()
            provider.id = provider.name = identity
            provider.fields = frozenset(fields)
            providers[identity] = provider
        patcher = patch('playlite.providers.discover_providers', return_value=providers)
        patcher.start()
        self.addCleanup(patcher.stop)

    def dialog(self, settings=True, save_ids=None):
        dialog = MetadataDownloader({'Name': 'Example', 'MetadataIds': {'First': '123'}},
            mode='metadata', settings_path=self.settings_path if settings else None, save_ids=save_ids)
        self.addCleanup(dialog.cache.cleanup)
        self.addCleanup(dialog.reject)
        return dialog

    def test_button_saves_source_matrix_without_downloading_or_saving_ids(self):
        save_ids = Mock()
        dialog = self.dialog(save_ids=save_ids)
        dialog.source_toggles['Name']['First'].setChecked(False)
        dialog.source_toggles['Links']['Second'].setChecked(False)
        dialog.id_fields['First'].setText('456')
        with patch.object(dialog, 'start_next_provider') as download:
            dialog.save_field_defaults_button.click()
            download.assert_not_called()
        save_ids.assert_not_called()
        self.assertEqual(dialog.pages.currentIndex(), 0)
        self.assertIn('saved', dialog.status.text())
        reopened = self.dialog()
        self.assertFalse(reopened.source_toggles['Name']['First'].isChecked())
        self.assertTrue(reopened.source_toggles['Name']['Second'].isChecked())
        self.assertFalse(reopened.source_toggles['Links']['Second'].isChecked())
        self.assertTrue(reopened.source_toggles['Description']['First'].isChecked())
        self.assertFalse(reopened.source_toggles['Description']['Second'].isEnabled())
        self.assertFalse(reopened.source_toggles['Description']['Second'].isChecked())
        self.assertEqual(reopened.id_fields['First'].text(), '123')
        self.assertEqual(reopened.column_toggles['Second'].checkState(), Qt.CheckState.PartiallyChecked)

    def test_all_unchecked_defaults_are_preserved(self):
        dialog = self.dialog()
        for provider in dialog.column_toggles:
            dialog.toggle_source_column(provider, False)
        dialog.save_field_defaults_button.click()
        reopened = self.dialog()
        self.assertFalse(any(toggle.isChecked() for toggles in reopened.source_toggles.values() for toggle in toggles.values()))
        self.assertEqual(reopened.settings.value('metadata/fields', type=list), [])

    def test_no_settings_disables_save_button(self):
        self.assertFalse(self.dialog(settings=False).save_field_defaults_button.isEnabled())

    def test_selections_persist_without_save_defaults(self):
        dialog = self.dialog()
        dialog.source_toggles['Name']['First'].setChecked(False)
        dialog.toggle_source_column('Second', False)
        reopened = self.dialog()
        self.assertFalse(reopened.source_toggles['Name']['First'].isChecked())
        self.assertTrue(reopened.source_toggles['Description']['First'].isChecked())
        self.assertFalse(any(toggles['Second'].isChecked() for toggles in reopened.source_toggles.values()))

    def test_provider_columns_fit_widest_styled_header(self):
        dialog = self.dialog()
        header = dialog.fields.horizontalHeader()
        header.setStyleSheet('QHeaderView { font-size: 24px; }')
        dialog.table_providers['Second'].name = 'Long metadata provider'
        dialog.fields.horizontalHeaderItem(2).setText('Long metadata provider')
        dialog.fit_metadata_columns()
        widths = [dialog.fields.columnWidth(column) for column, _ in dialog.provider_columns]
        self.assertEqual(len(set(widths)), 1)
        self.assertGreaterEqual(widths[0], header.fontMetrics().horizontalAdvance('Long metadata provider') + 40)
