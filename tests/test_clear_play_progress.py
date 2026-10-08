import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QMessageBox
from playlite.app import LibraryWindow
from playlite.game_detection import clear_play_progress
from playlite.settings import SettingsDialog

APP = QApplication.instance() or QApplication([])


class ClearPlayProgressTests(unittest.TestCase):
    def test_resets_latest_full_library_and_preserves_other_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            games = [dict(Id='one', Name='One', Playtime=42, PlayCount=3,
                          LastActivity='2026-10-08', CompletionStatus='Completed',
                          PlayActions=[dict(GameId='12345601')]),
                     dict(Id='hidden', Name='Hidden', Hidden=True, Playtime=90),
                     dict(Id='new', Name='Added after loading')]
            (data / 'library.json').write_text(json.dumps(games))
            saved = clear_play_progress(data, [dict(Id='stale')])
            self.assertEqual(saved, json.loads((data / 'library.json').read_text()))
            self.assertEqual(len(saved), 3)
            for original, reset in zip(games, saved):
                self.assertEqual(reset['Playtime'], 0)
                self.assertEqual(reset['PlayCount'], 0)
                self.assertIsNone(reset['LastActivity'])
                self.assertEqual({k: v for k, v in reset.items() if k not in ('Playtime', 'PlayCount', 'LastActivity')},
                                 {k: v for k, v in original.items() if k not in ('Playtime', 'PlayCount', 'LastActivity')})

    def test_failed_write_keeps_saved_history(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            path = data / 'library.json'
            original = json.dumps([dict(Id='one', Playtime=42)])
            path.write_text(original)
            with patch('playlite.storage.os.replace', side_effect=OSError('write failed')):
                with self.assertRaises(OSError):
                    clear_play_progress(data, [])
            self.assertEqual(path.read_text(), original)

    def test_warning_defaults_to_cancel_and_cancel_does_not_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            callback = Mock()
            dialog = SettingsDialog(QSettings(str(Path(directory) / 'ui.ini'), QSettings.Format.IniFormat), clear_progress=callback)
            def cancel(warning):
                self.assertEqual(warning.icon(), QMessageBox.Icon.Warning)
                self.assertEqual(warning.defaultButton(), warning.button(QMessageBox.StandardButton.Cancel))
                self.assertIn('ALL games', warning.text())
                return QMessageBox.StandardButton.Cancel
            with patch('playlite.settings.run_dialog', side_effect=cancel):
                dialog.clear_progress_button.click()
            callback.assert_not_called()
            dialog.reject()

    def test_confirmation_runs_immediately_and_settings_cancel_does_not_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            callback = Mock()
            dialog = SettingsDialog(QSettings(str(Path(directory) / 'ui.ini'), QSettings.Format.IniFormat), clear_progress=callback)
            with patch('playlite.settings.run_dialog', return_value=QMessageBox.StandardButton.Ok):
                dialog.clear_progress_button.click()
            callback.assert_called_once_with()
            dialog.reject()
            callback.assert_called_once_with()

    def test_running_sessions_restart_at_reset_time_and_view_refreshes(self):
        with tempfile.TemporaryDirectory() as directory:
            window = SimpleNamespace(data=Path(directory), games=[dict(Id='one', Playtime=42)],
                game_detection=SimpleNamespace(sessions={'one': dict(start=1, saved=10, counted=True, checkpoint=11)}, missing={'one': 11}),
                refresh_library=Mock())
            with patch('time.monotonic', return_value=100):
                LibraryWindow.clear_play_progress(window)
            self.assertEqual(window.games[0]['Playtime'], 0)
            self.assertEqual(window.game_detection.sessions['one'], dict(start=100, saved=0, counted=False, checkpoint=100))
            self.assertEqual(window.game_detection.missing['one'], 100)
            window.refresh_library.assert_called_once_with()
