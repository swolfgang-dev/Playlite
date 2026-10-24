from contextlib import closing
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from PyQt6.QtWidgets import QApplication, QCheckBox, QDialog, QWidget
from playlite.app import LibraryWindow
from playlite.lutris_delete import delete_entries
from playlite.lutris_history import refresh_history
from playlite.game_detection import record_playtime, clear_play_progress

APP = QApplication.instance() or QApplication([])


class LinkedLutrisTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root/'playlite'; self.data.mkdir()
        self.database = self.root/'pga.db'
        self.configs = self.root/'games'; self.configs.mkdir()
        self.installation = dict(database=self.database, config_directory=self.root, flatpak=False)
        patcher = patch('playlite.lutris_library.installations', return_value=[self.installation])
        patcher.start(); self.addCleanup(patcher.stop)
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('CREATE TABLE games(id INTEGER PRIMARY KEY,name TEXT,configpath TEXT,playtime REAL,lastplayed INTEGER)')
            db.execute('CREATE TABLE games_categories(game_id INTEGER, category_id INTEGER)')
            db.executemany('INSERT INTO games VALUES(?,?,?,?,?)', [(1,'Normal','normal',1.5,1000), (2,'Modded','modded',.25,2000)])
            db.execute('INSERT INTO games_categories VALUES(1,9)')
        for name in ('normal', 'modded'):
            (self.configs/(name+'.yml')).write_text('game:\n  exe: /keep/game\n')
        self.game = dict(Id='one', Name='Game', PlayCount=7, Playtime=99999,
                         PlayActions=[self.action(1), self.action(2), self.action(1)])
        self.path = self.data/'library.json'; self.path.write_text(json.dumps([self.game]))

    def action(self, identity):
        return dict(Name='Play', Integration='LutrisIntegration', GameId=str(identity), LutrisDatabase=str(self.database))

    def rows(self):
        with closing(sqlite3.connect(self.database)) as db:
            return db.execute('SELECT * FROM games ORDER BY id').fetchall()

    def test_history_uses_unique_entries_and_tracks_external_changes(self):
        result = refresh_history(self.data, [self.game])
        self.assertEqual(result[0]['Playtime'], 6300)
        self.assertEqual(result[0]['PlayCount'], 7)
        self.assertTrue(result[0]['LastActivity'].startswith('1969-12-31') or result[0]['LastActivity'].startswith('1970-01-01'))
        before = self.path.stat().st_mtime_ns
        self.assertEqual(refresh_history(self.data, result), result)
        self.assertEqual(self.path.stat().st_mtime_ns, before)
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('UPDATE games SET playtime=2,lastplayed=3000 WHERE id=2')
        result = refresh_history(self.data, result)
        self.assertEqual(result[0]['Playtime'], 12600)

    def test_missing_link_does_not_erase_history(self):
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('DELETE FROM games WHERE id=2')
        self.assertEqual(refresh_history(self.data, [self.game]), [self.game])

    def test_detector_does_not_double_count_lutris_sessions(self):
        result = record_playtime(self.data, [self.game], 'one', 30, 1, 'today')
        self.assertEqual(result, [self.game])
        self.assertEqual(self.rows()[0][3], 1.5)

    def test_reset_clears_lutris_and_does_not_reappear(self):
        reset = clear_play_progress(self.data, [self.game])
        self.assertEqual([r[3:] for r in self.rows()], [(0, None), (0, None)])
        self.assertEqual(refresh_history(self.data, reset), reset)

    def test_failed_reset_restores_lutris_history(self):
        original = self.rows()
        with patch('playlite.storage.atomic_json', side_effect=OSError('full')):
            with self.assertRaises(OSError): clear_play_progress(self.data, [self.game])
        self.assertEqual(self.rows(), original)
        self.assertEqual(json.loads(self.path.read_text()), [self.game])

    def test_delete_keeps_shared_entries_and_game_files(self):
        shared = dict(Id='other', PlayActions=[self.action(2)])
        game_file = self.root/'game.exe'; game_file.write_bytes(b'game')
        with delete_entries([self.game], [shared]): pass
        self.assertEqual([r[0] for r in self.rows()], [2])
        self.assertFalse((self.configs/'normal.yml').exists())
        self.assertTrue((self.configs/'modded.yml').exists())
        self.assertEqual(game_file.read_bytes(), b'game')
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT * FROM games_categories').fetchall(), [])

    def test_failed_library_save_restores_records_categories_and_configs(self):
        original = self.rows()
        with self.assertRaises(OSError):
            with delete_entries([self.game], []): raise OSError('library full')
        self.assertEqual(self.rows(), original)
        self.assertTrue((self.configs/'normal.yml').is_file())
        self.assertTrue((self.configs/'modded.yml').is_file())
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT * FROM games_categories').fetchall(), [(1,9)])

    def test_symlinked_configuration_is_rejected_without_removing_records(self):
        path = self.configs/'normal.yml'; path.unlink(); path.symlink_to(self.configs/'modded.yml')
        original = self.rows()
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            with delete_entries([self.game], []): pass
        self.assertEqual(self.rows(), original)
        self.assertTrue(path.is_symlink())

    def test_core_delete_checkbox_enabled_without_provider_plugin(self):
        window = QWidget(); self.addCleanup(window.close)
        window.data = self.data; window.games = [self.game]
        window.generic_plugins = []
        window.update_filter_choices = Mock(); window.refresh_library = Mock()
        def accept(dialog):
            checkbox = dialog.findChild(QCheckBox)
            self.assertTrue(checkbox.isEnabled())
            checkbox.setChecked(True)
            return QDialog.DialogCode.Accepted
        with patch('playlite.app.run_dialog', side_effect=accept):
            LibraryWindow.delete_games(window, [self.game])
        self.assertEqual(self.rows(), [])
        self.assertEqual(json.loads(self.path.read_text()), [])

    def test_unchecked_delete_keeps_launcher_entries(self):
        window = QWidget(); self.addCleanup(window.close)
        window.data = self.data; window.games = [self.game]; window.generic_plugins = []
        window.update_filter_choices = Mock(); window.refresh_library = Mock()
        original = self.rows()
        with patch('playlite.app.run_dialog', return_value=QDialog.DialogCode.Accepted):
            LibraryWindow.delete_games(window, [self.game])
        self.assertEqual(self.rows(), original)
        self.assertEqual(json.loads(self.path.read_text()), [])
