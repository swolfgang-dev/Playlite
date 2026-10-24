import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication, QDialog
from playlite.lutris_library import read_entries, import_entry, library_databases, installations
from playlite.lutris_import import LutrisImportDialog

APP = QApplication.instance() or QApplication([])


class LutrisImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / 'lutris/pga.db'
        self.database.parent.mkdir()
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('CREATE TABLE games(id INTEGER PRIMARY KEY, name TEXT, installed INTEGER, runner TEXT)')
            db.executemany('INSERT INTO games VALUES (?, ?, ?, ?)', [(42, 'Example', 1, 'wine'), (84, 'Another', 0, 'steam')])
        self.data = self.root / 'playlite'
        installation = patch('playlite.lutris_library.installations', return_value=[{'database': self.database, 'flatpak': False, 'config_directory': self.database.parent}])
        installation.start()
        self.addCleanup(installation.stop)
        plugins = patch('playlite.providers.discover_plugins', return_value={})
        plugins.start()
        self.addCleanup(plugins.stop)

    def test_import_persists_only_entry_identity_and_keeps_lutris_unchanged(self):
        before = hashlib.sha256(self.database.read_bytes()).hexdigest()
        games, identity = import_entry(self.data, [], self.database, 42)
        game = next(game for game in games if game['Id'] == identity)
        self.assertEqual(game['Name'], 'Example')
        self.assertEqual(game['PlayActions'], [{'Name': 'Play', 'Integration': 'LutrisIntegration', 'GameId': '42', 'LutrisDatabase': str(self.database)}])
        self.assertNotIn('Executable', game)
        self.assertNotIn('Prefix', game)
        self.assertEqual(json.loads((self.data / 'library.json').read_text()), games)
        self.assertEqual(hashlib.sha256(self.database.read_bytes()).hexdigest(), before)
        self.assertEqual(list(self.database.parent.iterdir()), [self.database])

    def test_duplicate_is_rechecked_against_saved_library(self):
        games, _ = import_entry(self.data, [], self.database, 42)
        with self.assertRaisesRegex(ValueError, 'already'):
            import_entry(self.data, [], self.database, 42)
        self.assertEqual(len(json.loads((self.data / 'library.json').read_text())), 1)

    def test_deleted_selection_is_not_imported(self):
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('DELETE FROM games WHERE id=42')
        with self.assertRaisesRegex(ValueError, 'no longer exists'):
            import_entry(self.data, [], self.database, 42)
        self.assertFalse(self.data.exists())

    def test_missing_and_invalid_databases_have_useful_errors(self):
        with self.assertRaisesRegex(ValueError, 'not found'):
            read_entries(self.root / 'missing.db')
        bad = self.root / 'bad.db'
        bad.write_bytes(b'not a database')
        with self.assertRaisesRegex(ValueError, 'Could not read'):
            read_entries(bad)

    def test_dialog_filters_existing_and_searches_entries(self):
        games = [{'PlayActions': [{'Integration': 'LutrisIntegration', 'GameId': '42'}]}]
        with patch('playlite.lutris_import.library_databases', return_value=[self.database]):
            dialog = LutrisImportDialog(games)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.entries.count(), 1)
        self.assertIn('Another', dialog.entries.item(0).text())
        dialog.entries.setCurrentRow(0)
        self.assertTrue(dialog.import_button.isEnabled())
        dialog.search.setText('Example')
        self.assertFalse(dialog.import_button.isEnabled())
        dialog.search.setText('another')
        dialog.select()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.selected_entry['id'], '84')

    def test_both_native_and_flatpak_libraries_are_found(self):
        home = self.root / 'home'
        flatpak = home / '.var/app/net.lutris.Lutris/data/lutris/pga.db'
        flatpak.parent.mkdir(parents=True)
        flatpak.touch()
        with patch('playlite.lutris_library.host_environment', return_value={'HOME': str(home), 'XDG_DATA_HOME': str(self.root)}), patch('playlite.lutris_library.installations', new=installations):
            self.assertEqual(library_databases(), [self.database, flatpak])

    def test_dialog_handles_missing_library_without_enabling_import(self):
        with patch('playlite.lutris_import.library_databases', return_value=[]):
            dialog = LutrisImportDialog([])
        self.addCleanup(dialog.close)
        self.assertFalse(dialog.import_button.isEnabled())
        self.assertIn('No Lutris library found', dialog.status.text())

    def test_offline_library_is_rejected_before_saving_unlaunchable_entry(self):
        with patch('playlite.lutris_library.installations', return_value=[]):
            with self.assertRaisesRegex(ValueError, 'active library'):
                import_entry(self.data, [], self.database, '42')
        self.assertFalse(self.data.exists())
