import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication, QLineEdit
from playlite.lutris_library import entry_details
from playlite.play_actions import LutrisActionSettings

APP = QApplication.instance() or QApplication([])


class LutrisDetailsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / 'pga.db'
        self.config = self.root / 'config'
        (self.config / 'games').mkdir(parents=True)
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('CREATE TABLE games(id INTEGER PRIMARY KEY, name, runner, configpath, executable)')
            db.executemany('INSERT INTO games VALUES (?, ?, ?, ?, ?)', [(1, 'Steam Game', 'steam', 'steam-game', ''), (2, 'Wine Game', 'wine', 'wine-game', '/old/game.exe')])
        (self.config / 'games/steam-game.yml').write_text('game:\n  appid: 12345\n')
        self.wine = self.config / 'games/wine-game.yml'
        self.wine.write_text('game:\n  exe: /games/example/game.exe\n  prefix: /prefixes/example\n')
        patcher = patch('playlite.lutris_library.installations', return_value=[{'database': self.database, 'config_directory': self.config, 'flatpak': True}])
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_steam_shows_app_id_without_wine_fields(self):
        details = dict(entry_details(self.database, '1'))
        self.assertEqual(details['Steam app ID'], '12345')
        self.assertEqual(details['Runner'], 'Steam')
        self.assertNotIn('Wine prefix', details)
        self.assertNotIn('Executable', details)

    def test_wine_reads_live_config_instead_of_stale_database_executable(self):
        before = self.database.read_bytes()
        details = dict(entry_details(self.database, '2'))
        self.assertEqual(details['Executable'], '/games/example/game.exe')
        self.assertEqual(details['Wine prefix'], '/prefixes/example')
        self.assertEqual(self.database.read_bytes(), before)

    def test_refresh_and_selection_change_update_read_only_details(self):
        identity = QLineEdit('2')
        widget = LutrisActionSettings({'LutrisDatabase': str(self.database)}, identity)
        self.addCleanup(widget.close)
        self.assertEqual(widget.detail_values['Wine prefix'].text(), '/prefixes/example')
        self.wine.write_text('game:\n  exe: /changed.exe\n  prefix: /changed-prefix\n')
        widget.refresh_details()
        self.assertEqual(widget.detail_values['Executable'].text(), '/changed.exe')
        self.assertEqual(widget.detail_values['Wine prefix'].text(), '/changed-prefix')
        self.assertEqual(widget.collect(), {'LutrisDatabase': str(self.database)})
        identity.setText('1')
        self.assertEqual(widget.detail_values['Steam app ID'].text(), '12345')
        self.assertNotIn('Wine prefix', widget.detail_values)

    def test_bad_config_or_deleted_entry_shows_inline_error(self):
        identity = QLineEdit('2')
        self.wine.write_text('game: [broken')
        widget = LutrisActionSettings({'LutrisDatabase': str(self.database)}, identity)
        self.addCleanup(widget.close)
        self.assertIn('Could not read', widget.details_error.text())
        identity.setText('999')
        self.assertIn('no longer exists', widget.details_error.text())
        self.assertEqual(widget.detail_values, {})

    def test_configuration_filename_cannot_escape_games_directory(self):
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE games SET configpath='../outside' WHERE id=2")
        with self.assertRaisesRegex(ValueError, 'invalid configuration'):
            entry_details(self.database, '2')

    def test_shared_configuration_lookup_uses_the_entries_active_config_directory(self):
        from playlite.lutris_library import configuration_path
        self.assertEqual(configuration_path(self.database, '2'), self.wine)
        self.assertEqual(configuration_path(None, '2'), self.wine)
        with self.assertRaises(ValueError):
            configuration_path(self.database, '999')
        self.wine.unlink()
        self.wine.symlink_to(self.config / 'games/steam-game.yml')
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            configuration_path(self.database, '2')
