import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PyQt6.QtWidgets import QApplication, QLabel
from playlite.app import LibraryWindow
from playlite.installation import record_installation_size

APP = QApplication.instance() or QApplication([])


class InstallationSizeTests(unittest.TestCase):
    def test_scan_merges_latest_entries_and_does_not_restore_removed_games(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            old = [{'Id': 'removed', 'InstallDirectory': '/games/old'}]
            latest = [{'Id': 'kept', 'Name': 'Edited', 'Playtime': 99,
                       'InstallDirectory': '/games/shared'}]
            path = data / 'library.json'
            path.write_text(json.dumps(latest))
            saved = record_installation_size(data, old, '/games/shared', 0)
            self.assertEqual(saved, [dict(latest[0], InstallSize=0)])
            self.assertEqual(json.loads(path.read_text()), saved)
            path.write_text('[]')
            self.assertEqual(record_installation_size(data, old, '/games/old', 10), [])
            self.assertEqual(path.read_text(), '[]')

    def test_repeated_selection_shares_a_scan_and_stale_folder_is_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            folder = data / 'game'
            folder.mkdir()
            (folder / 'content').write_bytes(b'game')
            window = LibraryWindow(data)
            window.game_detection.stop()
            game = dict(Id='one', Name='Example', InstallDirectory=str(folder))
            window.games = [game]
            window.current = game
            window.installation_size_label = QLabel(window)
            pool = Mock()
            with patch('playlite.app.QThreadPool.globalInstance', return_value=pool):
                window.show_installation_size(game)
                window.show_installation_size(game)
            pool.start.assert_called_once()
            latest = dict(game, InstallDirectory='/changed/folder', Playtime=77)
            path = data / 'library.json'
            path.write_text(json.dumps([latest]))
            pool.start.call_args.args[0].run()
            self.assertEqual(json.loads(path.read_text()), [latest])
            self.assertEqual(window.games, [latest])
            self.assertFalse(window.size_tasks)
            window.close()
