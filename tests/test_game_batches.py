import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import patch, Mock
from PyQt6.QtCore import Qt, QTimer, QThreadPool
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QAbstractItemView, QCheckBox, QDialog, QMenu
from PyQt6.QtTest import QTest
from playlite.app import LibraryWindow, ArtworkPage
from playlite.editor import MetadataEditor

APP = QApplication.instance() or QApplication([])


def wait(predicate):
    deadline = time.monotonic() + 3
    while not predicate() and time.monotonic() < deadline:
        APP.processEvents()
        time.sleep(.005)
    assert predicate()


class GameBatchTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.data = Path(self.directory.name)
        self.games = [dict(Id=str(i), Name='Game ' + str(i)) for i in range(3)]
        (self.data / 'library.json').write_text(json.dumps(self.games))
        self.window = LibraryWindow(self.data)
        self.window.game_detection.stop()
        self.window.resize(1400, 1000)
        self.window.show()
        QTest.qWait(30)
        self.addCleanup(self.window.close)

    def test_editor_navigation_saves_and_keeps_displayed_order_and_tab(self):
        self.window.order.setChecked(True)
        self.window.refresh_library()
        self.window.list.setCurrentRow(0)
        shown = [self.window.list.item(i).data(Qt.ItemDataRole.UserRole)['Id']
                 for i in range(self.window.list.count())]
        visits = []
        observer = Mock()
        observer.name = "Observer"
        observer.game_actions.return_value = []
        self.window.generic_plugins = [observer]
        def edit(dialog):
            visits.append(dialog.game['Id'])
            if len(visits) == 1:
                self.assertFalse(dialog.previous_game.isEnabled())
                dialog.fields['Name'].setText('AAA')
                dialog.tabs.setCurrentIndex(1)
                dialog.next_game.click()
            elif len(visits) == 2:
                self.assertEqual(dialog.tabs.currentIndex(), 1)
                dialog.previous_game.click()
            else:
                self.assertEqual(dialog.fields['Name'].text(), 'AAA')
                dialog.reject()
            return dialog.result()
        with patch('playlite.app.run_dialog', side_effect=edit):
            self.window.edit_game()
        self.assertEqual(visits, [shown[0], shown[1], shown[0]])
        self.assertEqual(observer.after_game_updated.call_count, 2)
        self.assertEqual(observer.after_game_updated.call_args_list[0].args[1]['Name'], 'AAA')
        saved = json.loads((self.data / 'library.json').read_text())
        self.assertEqual(next(g for g in saved if g['Id'] == shown[0])['Name'], 'AAA')

    def test_editor_navigation_stays_on_current_game_when_saving_fails(self):
        current = self.window.current['Id']
        visits = []
        observer = Mock()
        observer.name = "Observer"
        observer.game_actions.return_value = []
        self.window.generic_plugins = [observer]
        def edit(dialog):
            visits.append(dialog.game['Id'])
            if len(visits) == 1:
                dialog.fields['Name'].setText('Unsaved edit')
                dialog.next_game.click()
            else:
                self.assertIn('Could not save game', dialog.error.text())
                self.assertEqual(dialog.fields['Name'].text(), 'Unsaved edit')
                dialog.reject()
            return dialog.result()
        with patch('playlite.app.run_dialog', side_effect=edit), patch('playlite.app.save_game', side_effect=OSError('disk full')):
            self.window.edit_game()
        self.assertEqual(visits, [current, current])
        observer.after_game_updated.assert_not_called()
        self.assertEqual(json.loads((self.data / 'library.json').read_text()), self.games)

    def test_archive_information_is_only_shown_when_editing(self):
        from plugin_test_support import require_plugin
        require_plugin('GameArchiver')
        from playlite.add_game import AddGameEditor
        from PyQt6.QtWidgets import QLabel, QPushButton
        added = AddGameEditor(None, self.data, installation_method='Manual')
        self.addCleanup(added.reject)
        self.assertFalse(hasattr(added, 'archived'))
        self.assertFalse(any(label.text() == 'Archive information' for label in added.findChildren(QLabel)))
        edited = MetadataEditor(self.games[0], self.data)
        self.addCleanup(edited.reject)
        self.assertTrue(hasattr(edited, 'archived'))
        self.assertTrue(any(button.text() == 'Browse…' and button.height() == 40 for button in edited.findChildren(QPushButton)))
        self.assertEqual(self.window.list.spacing(), 3)

    def test_saving_added_game_selects_it_and_reveals_it_through_filters(self):
        from types import SimpleNamespace
        from PyQt6.QtWidgets import QLabel
        for mode in ('list', 'grid'):
            self.window.view.setCurrentIndex(self.window.view.findData(mode))
            self.window.favorites_filter.setChecked(True)
            game = dict(Id='added-' + mode, Name='Added game', IsInstalled=True)
            editor = SimpleNamespace(result_game=game, download_caches=[], generic_plugins=[], error=QLabel())
            with patch('playlite.add_game.AddGameEditor', return_value=editor), patch('playlite.app.run_dialog', return_value=QDialog.DialogCode.Accepted):
                self.window.add_manual_game()
            self.assertEqual(self.window.current['Id'], game['Id'])
            self.assertEqual([g['Id'] for g in self.window.selected_games()], [game['Id']])
            self.assertFalse(self.window.favorites_filter.isChecked())
            self.assertEqual(self.window.list.currentItem().data(Qt.ItemDataRole.UserRole)['Id'], game['Id'])
            self.assertTrue(any(saved['Id'] == game['Id'] for saved in json.loads((self.data / 'library.json').read_text())))

    def test_grid_and_list_support_control_click_and_preserve_selection_on_view_switch(self):
        window = self.window
        self.assertEqual(window.list.selectionMode(), QAbstractItemView.SelectionMode.ExtendedSelection)
        for view in ('list', 'grid'):
            window.view.setCurrentIndex(window.view.findData(view))
            QTest.qWait(30)
            window.list.clearSelection()
            for index in (0, 1):
                pos = window.list.visualItemRect(window.list.item(index)).center()
                QTest.mouseClick(window.list.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, pos)
            self.assertEqual({g['Id'] for g in window.selected_games()}, {'0', '1'})
            window.refresh_library()
            self.assertEqual({g['Id'] for g in window.selected_games()}, {'0', '1'})
        QTest.mouseClick(window.list.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, window.list.visualItemRect(window.list.item(0)).center())

    def test_right_click_keeps_the_selection_and_calls_batch_plugin_actions(self):
        from types import SimpleNamespace
        window = self.window
        window.list.item(0).setSelected(True)
        window.list.item(1).setSelected(True)
        captured = []
        plugin = SimpleNamespace(augment_game_view=lambda *args: None, name='Example', game_actions=lambda w, game: [], batch_game_actions=lambda w, games: captured.append(games) or [('Batch', lambda: None)])
        window.generic_plugins = [plugin]
        menu = QMenu(window)
        with patch('playlite.app.game_context_menu', return_value=menu) as build:
            window.show_game_context_menu(window.list.visualItemRect(window.list.item(1)).center())
        self.assertEqual(len(window.selected_games()), 2)
        self.assertEqual(len(captured[0]), 2)
        self.assertIsNone(build.call_args.args[1])
        menu.close()

    def test_batch_delete_keeps_game_files_and_remaining_entries(self):
        folder = self.data / 'game-files'
        folder.mkdir()
        (folder / 'keep').write_bytes(b'original')
        with patch('playlite.app.run_dialog', return_value=QDialog.DialogCode.Accepted):
            self.window.delete_games(self.games[:2])
        self.assertEqual([g['Id'] for g in self.window.games], ['2'])
        self.assertEqual((folder / 'keep').read_bytes(), b'original')

    def test_batch_delete_rolls_back_launcher_entries_if_library_write_fails(self):
        from types import SimpleNamespace
        restored = []
        provider = SimpleNamespace(supports_entry_deletion=True, owns=lambda g: True,
            delete_entry=lambda g: g['Id'], restore_deleted_entry=lambda backup: restored.append(backup))
        self.window.game_providers = [provider]
        def confirm(dialog):
            for check in dialog.findChildren(QCheckBox):
                check.setChecked(True)
            return QDialog.DialogCode.Accepted
        with patch('playlite.app.run_dialog', side_effect=confirm), patch('playlite.storage.atomic_json', side_effect=OSError('disk')), patch('playlite.app.show_warning'):
            self.window.delete_games(self.games[:2])
        self.assertEqual(restored, ['1', '0'])
        self.assertEqual(json.loads((self.data / 'library.json').read_text()), self.games)

    def test_archive_editor_records_state_without_moving_files(self):
        from plugin_test_support import require_plugin
        require_plugin('GameArchiver')
        game = dict(Id='a', Name='Example', InstallDirectory=str(self.data / 'original'))
        editor = MetadataEditor(game, self.data)
        editor.archived.setChecked(True)
        editor.archive_path.setText(str(self.data / 'archive'))
        result = editor.collect()
        self.assertFalse(result['IsInstalled'])
        self.assertEqual(result['ArchiveOriginalDirectory'], game['InstallDirectory'])
        self.assertIn('Archived', result['Tags'])
        from playlite.editor import save_game
        (self.data / 'library.json').write_text(json.dumps([game]))
        stored = save_game(self.data, [game], result)
        self.assertEqual(stored[0]['ArchivePath'], result['ArchivePath'])
        self.assertNotIn('_ArchiveEditBase', stored[0])
        self.assertFalse((self.data / 'archive').exists())
        editor.reject()
        self.window.games = stored
        self.window.refresh_library()
        self.assertIsNotNone(self.window.findChild(__import__('PyQt6.QtWidgets', fromlist=['QLabel']).QLabel, 'archiveIndicator'))


class BackgroundAnimationTests(unittest.TestCase):
    def test_background_preparation_does_not_block_gui_and_stale_result_is_ignored(self):
        page = ArtworkPage()
        release = threading.Event()
        started = threading.Event()
        def prepare(image, *args):
            if image.pixelColor(0, 0) == Qt.GlobalColor.red:
                started.set()
                release.wait(3)
            return image
        red = QPixmap(2, 2); red.fill(Qt.GlobalColor.red)
        blue = QPixmap(2, 2); blue.fill(Qt.GlobalColor.blue)
        with patch('playlite.background_art.prepare', side_effect=prepare):
            page.set_background(red)
            self.assertTrue(started.wait(1))
            tick = []
            QTimer.singleShot(0, lambda: tick.append(True))
            wait(lambda: tick)
            page.set_background(blue)
            wait(lambda: not page.background.isNull())
            self.assertEqual(page.background.toImage().pixelColor(0, 0), Qt.GlobalColor.blue)
            release.set()
            wait(lambda: not page.background_tasks)
            self.assertEqual(page.background.toImage().pixelColor(0, 0), Qt.GlobalColor.blue)
