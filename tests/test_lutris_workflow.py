"""Exercise the real dialogs, library window and persistent stores together."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import vdf
from PyQt6.QtCore import QSettings, QThreadPool
from PyQt6.QtWidgets import QApplication, QDialog, QDialogButtonBox
from playlite.app import LibraryWindow
from playlite.add_game import AddGameMethods
from playlite.editor import MetadataEditor
from playlite.lutris_add_dialog import AddExecutableDialog
from playlite.lutris_steam_dialog import AddSteamDialog
from playlite.lutris_import import LutrisImportDialog
from playlite.lutris_add import PendingExecutable

APP=QApplication.instance() or QApplication([])


class WholeWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.data=self.root/'playlite';self.data.mkdir()
        self.steam=self.root/'Steam'
        self.folder=self.steam/'steamapps/common/ExampleGame';self.folder.mkdir(parents=True)
        self.exe=self.folder/'game.exe';self.exe.write_bytes(b'never execute')
        self.manifest=self.steam/'steamapps/appmanifest_42.acf'
        self.manifest.write_text(vdf.dumps({'AppState':{'appid':'42','name':'Example Game','installdir':'ExampleGame','StateFlags':'4'}}))
        self.database=self.root/'pga.db'
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('CREATE TABLE games(id INTEGER PRIMARY KEY,name,sortname,slug,platform,runner,executable,directory,installed,installed_at,configpath,playtime,service,service_id)')
        self.installation={'database':self.database,'flatpak':False,'config_directory':self.root/'config'}
        for module in ('lutris_add','lutris_library','lutris_launch','lutris_add_dialog','lutris_steam_dialog'):
            patcher=patch('playlite.'+module+'.installations',return_value=[self.installation]);patcher.start();self.addCleanup(patcher.stop)
        patcher=patch('playlite.providers.discover_plugins',return_value={});patcher.start();self.addCleanup(patcher.stop)
        patcher=patch('playlite.steam_library.host_environment',return_value={'HOME':str(self.root/'home'),'XDG_DATA_HOME':str(self.root)});patcher.start();self.addCleanup(patcher.stop)
        settings=QSettings(str(self.data/'ui.ini'),QSettings.Format.IniFormat)
        settings.setValue('installation/defaultFolder',str(self.steam/'steamapps/common'))
        settings.setValue('installation/defaultPrefixFolder',str(self.root/'prefixes'));settings.sync()
        self.window=LibraryWindow(self.data)
        self.addCleanup(self.cleanup_window)
        self.mode='exe';self.steam_id='';self.cancel=False
        self.cancel_dialog=None
        self.edit_callback=None
        for module in ('app','lutris_add_dialog','lifecycle'):
            patcher=patch('playlite.'+module+'.run_dialog',side_effect=self.interact);patcher.start();self.addCleanup(patcher.stop)
        patcher=patch('playlite.lutris_add_dialog.choose_file',return_value=(str(self.exe),''));self.choose_file=patcher.start();self.addCleanup(patcher.stop)
        patcher=patch('playlite.app.show_warning');self.warning=patcher.start();self.addCleanup(patcher.stop)

    def cleanup_window(self):
        self.window.close()
        QThreadPool.globalInstance().waitForDone(3000)
        APP.processEvents()

    def interact(self, dialog):
        if self.cancel or (self.cancel_dialog is not None and isinstance(dialog,self.cancel_dialog)):
            dialog.reject();return QDialog.DialogCode.Rejected
        if isinstance(dialog,AddGameMethods):
            if dialog.windowTitle()=='Choose play action':
                dialog.choose(self.window.current['PlayActions'][0])
            else:dialog.choose(self.mode)
        elif isinstance(dialog,AddExecutableDialog):
            dialog.steam_id.setText(self.steam_id);dialog.save()
        elif isinstance(dialog,AddSteamDialog):
            dialog.games.setCurrentRow(0);dialog.select()
        elif isinstance(dialog,LutrisImportDialog):
            dialog.entries.setCurrentRow(0);dialog.select()
        elif self.edit_callback is not None and dialog.findChild(MetadataEditor) is not None:
            self.edit_callback(dialog.findChild(MetadataEditor))
        else:raise AssertionError(type(dialog).__name__)
        return dialog.result()

    def saved(self):
        return json.loads((self.data/'library.json').read_text())

    def test_main_executable_add_populates_folder_and_launches_saved_action(self):
        self.window.add_game()
        self.warning.assert_not_called()
        self.assertEqual(self.choose_file.call_args.args[2],str(self.steam/'steamapps/common'))
        game=self.saved()[0]
        self.assertEqual(game.get('InstallDirectory'),str(self.folder))
        with patch('playlite.lutris_launch.shutil.which',return_value='/usr/bin/lutris'),patch('playlite.lutris_launch.subprocess.Popen') as spawn:
            self.assertTrue(self.window.play_button.isEnabled())
            self.window.play_button.click()
        self.warning.assert_not_called()
        self.assertEqual(spawn.call_args.args[0],['/usr/bin/lutris','lutris:rungameid/'+game['PlayActions'][0]['GameId']])

    def test_metadata_association_survives_reselect_and_launch(self):
        self.window.add_game()
        editor=MetadataEditor(self.window.current,self.data,self.window)
        self.addCleanup(editor.close)
        editor.save_metadata_ids({'SteamMetadata':'42'})
        self.assertEqual(self.window.current['PlayActions'][0]['GameId'],'4201')
        self.window.select_game(self.window.list.currentItem())
        with patch('playlite.lutris_launch.shutil.which',return_value='/usr/bin/lutris'),patch('playlite.lutris_launch.subprocess.Popen') as spawn:
            self.window.play_game()
        self.warning.assert_not_called()
        self.assertEqual(spawn.call_args.args[0],['/usr/bin/lutris','lutris:rungameid/4201'])

    def test_main_steam_add_migrates_existing_random_and_keeps_both_launchable(self):
        self.window.add_game()
        self.mode='steam';self.window.add_game()
        self.warning.assert_not_called()
        self.assertEqual(len(self.saved()),2)
        self.assertEqual({g['PlayActions'][0]['GameId'] for g in self.saved()},{'4201','4202'})
        for index in range(self.window.list.count()):
            self.window.list.setCurrentRow(index)
            with patch('playlite.lutris_launch.shutil.which',return_value='/usr/bin/lutris'),patch('playlite.lutris_launch.subprocess.Popen') as spawn:
                self.window.play_game()
            self.assertTrue(spawn.called)
        self.warning.assert_not_called()

    def test_associated_executable_add_saves_metadata_and_wine_runner(self):
        self.steam_id='42';self.window.add_game()
        self.warning.assert_not_called()
        self.assertEqual(self.saved()[0]['MetadataIds'],{'SteamMetadata':'42'})
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT id,runner FROM games').fetchone(),(4201,'wine'))

    def test_cancel_main_add_creates_no_game_or_prefix(self):
        self.cancel=True;self.window.add_game()
        self.assertFalse((self.data/'library.json').exists())
        self.assertFalse((self.root/'prefixes').exists())

    def test_existing_import_preserves_lutris_and_launches(self):
        from playlite.lutris_add import ExecutablePlan,register_executable
        plan=ExecutablePlan('Existing',self.exe,self.folder,self.root/'prefixes/existing',self.database)
        with register_executable(plan) as action:pass
        before=self.database.read_bytes()
        self.mode='import';self.window.add_game()
        self.warning.assert_not_called()
        self.assertEqual(self.database.read_bytes(),before)
        self.assertEqual(self.saved()[0]['PlayActions'][0]['GameId'],action['GameId'])

    def test_saved_action_editor_cannot_reintroduce_old_ids_after_migration(self):
        self.window.add_game()
        editor=MetadataEditor(self.window.current,self.data,self.window)
        self.addCleanup(editor.close)
        editor.play_actions.choose_steam()
        editor.result_game=editor.collect()
        self.window.games=editor.play_actions.save_with_removals(lambda:self._save_editor(editor),editor.result_game)
        self.assertEqual([a['GameId'] for a in editor.play_actions.collect()],
                         [a['GameId'] for a in editor.result_game['PlayActions']])

    def _save_editor(self,editor):
        from playlite.game_storage import save_game
        return save_game(self.data,self.window.games,editor.result_game)

    def test_main_add_failure_cleans_registration_then_retry_succeeds(self):
        with patch('playlite.game_storage.atomic_json',side_effect=OSError('disk error')):
            self.window.add_game()
        self.warning.assert_called_once()
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM games').fetchone()[0],0)
        self.assertFalse((self.root/'prefixes').exists())
        self.warning.reset_mock()
        self.window.add_game()
        self.warning.assert_not_called()
        self.assertEqual(len(self.saved()),1)

    def test_cancel_executable_confirmation_has_no_external_effects(self):
        self.cancel_dialog=AddExecutableDialog
        self.window.add_game()
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM games').fetchone()[0],0)
        self.assertFalse((self.root/'prefixes').exists())
        self.assertFalse((self.data/'library.json').exists())

    def test_cancel_steam_selection_has_no_external_effects(self):
        self.mode='steam';self.cancel_dialog=AddSteamDialog
        self.window.add_game()
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM games').fetchone()[0],0)
        self.assertFalse((self.data/'library.json').exists())

    def test_real_edit_save_sets_default_and_dispatches_both_actions(self):
        self.window.add_game()
        def edit(editor):
            editor.play_actions.choose_steam()
            editor.play_actions.cards[-1].default.setChecked(True)
            editor.save()
            self.assertFalse(editor.error.text(),editor.error.text())
        self.edit_callback=edit
        self.window.edit_game()
        self.warning.assert_not_called()
        actions=self.saved()[0]['PlayActions']
        self.assertEqual([a['GameId'] for a in actions],['4202','4201'])
        self.assertTrue(actions[1]['Default'])
        with patch('playlite.lutris_launch.shutil.which',return_value='/usr/bin/lutris'),patch('playlite.lutris_launch.subprocess.Popen') as spawn:
            self.window.play_button.click()
            self.assertEqual(spawn.call_args.args[0],['/usr/bin/lutris','lutris:rungameid/4201'])
            self.window.play_game(choose_action=True)
            self.assertEqual(spawn.call_args.args[0],['/usr/bin/lutris','lutris:rungameid/4202'])
        self.warning.assert_not_called()

    def test_cancel_edit_after_adding_action_does_not_create_entry(self):
        self.window.add_game()
        before=(self.data/'library.json').read_bytes()
        def edit(editor):
            editor.play_actions.choose_steam()
            editor.reject()
        self.edit_callback=edit
        self.window.edit_game()
        self.assertEqual((self.data/'library.json').read_bytes(),before)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM games').fetchone()[0],1)

    def test_metadata_migration_refreshes_other_games_in_library_view(self):
        from PyQt6.QtCore import Qt
        self.window.add_game()
        first=self.window.current['Id']
        alternate=self.folder/'alternate.exe';alternate.touch()
        self.choose_file.return_value=(str(alternate),'')
        self.window.add_game()
        second=self.window.current['Id']
        item=next(self.window.list.item(i) for i in range(self.window.list.count()) if self.window.list.item(i).data(Qt.ItemDataRole.UserRole)['Id']==first)
        self.window.list.setCurrentItem(item)
        editor=MetadataEditor(self.window.current,self.data,self.window)
        self.addCleanup(editor.close)
        editor.save_metadata_ids({'SteamMetadata':'42'})
        item=next(self.window.list.item(i) for i in range(self.window.list.count()) if self.window.list.item(i).data(Qt.ItemDataRole.UserRole)['Id']==second)
        self.window.list.setCurrentItem(item)
        with patch('playlite.lutris_launch.shutil.which',return_value='/usr/bin/lutris'),patch('playlite.lutris_launch.subprocess.Popen') as spawn:
            self.window.play_game()
        self.warning.assert_not_called()
        self.assertTrue(spawn.called)

    def test_removing_unsaved_action_never_registers_it(self):
        self.window.add_game()
        original=self.saved()[0]['PlayActions'][0]['GameId']
        def edit(editor):
            editor.play_actions.choose_steam()
            editor.play_actions.remove(editor.play_actions.cards[-1])
            editor.save()
        self.edit_callback=edit
        self.window.edit_game()
        self.assertEqual([a['GameId'] for a in self.saved()[0]['PlayActions']],[original])
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM games').fetchone()[0],1)

    def test_reordering_pending_actions_preserves_ids_and_default(self):
        self.window.add_game()
        def edit(editor):
            editor.play_actions.choose_steam()
            steam=editor.play_actions.cards[-1]
            steam.default.setChecked(True)
            editor.play_actions.move(steam,-1)
            editor.save()
            self.assertFalse(editor.error.text(),editor.error.text())
            self.assertTrue(steam.settings.choose_button.isEnabled())
        self.edit_callback=edit
        self.window.edit_game()
        actions=self.saved()[0]['PlayActions']
        self.assertEqual([a['GameId'] for a in actions],['4201','4202'])
        self.assertTrue(actions[0]['Default'])
        self.warning.assert_not_called()
