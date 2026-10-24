import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from contextlib import closing
from dataclasses import replace
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch, Mock
import yaml
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication
from playlite.lutris_add import ExecutablePlan, PendingExecutable, register_executable, installation_folder, prefix_slug
from playlite.lutris_add_dialog import AddExecutableDialog, choose_executable_entry
from playlite.play_actions import PlayActionsEditor
from playlite.lutris_library import entry_details

APP = QApplication.instance() or QApplication([])


class LutrisAddTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.install = self.root / 'installed'
        self.folder = self.install / 'HollowKnightSilksong'
        self.exe = self.folder / 'bin/game.exe'
        self.exe.parent.mkdir(parents=True)
        self.exe.write_bytes(b'untouched executable')
        self.data = self.root / 'playlite'
        self.data.mkdir()
        settings = QSettings(str(self.data / 'ui.ini'), QSettings.Format.IniFormat)
        settings.setValue('installation/defaultFolder', str(self.install))
        settings.setValue('installation/defaultPrefixFolder', str(self.root / 'prefixes'))
        settings.sync()
        self.database = self.root / 'pga.db'
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('CREATE TABLE games(id INTEGER PRIMARY KEY, name, sortname, slug, platform, runner, executable, directory, installed, installed_at, configpath, playtime, service)')
        self.configuration = self.root / 'lutris-config'
        self.installation = {'database': self.database, 'flatpak': False, 'config_directory': self.configuration}
        for module in ('lutris_add', 'lutris_add_dialog', 'lutris_library'):
            patcher = patch('playlite.'+module+'.installations', return_value=[self.installation])
            patcher.start()
            self.addCleanup(patcher.stop)
        self.plan = ExecutablePlan('Hollow Knight Silksong', self.exe, self.folder,
                                   self.root / 'prefixes/hollow-knight-silksong', self.database)

    def count(self):
        with closing(sqlite3.connect(self.database)) as db:
            return db.execute('SELECT COUNT(*) FROM games').fetchone()[0]

    def test_slug_and_installation_root_match_old_autofill(self):
        self.assertEqual(prefix_slug("HollowKnightSilksong"), 'hollow-knight-silksong')
        self.assertEqual(prefix_slug("Tom’s_HTTPGame_2"), 'toms-http-game-2')
        self.assertEqual(installation_folder(self.exe, self.install), self.folder)
        self.assertEqual(installation_folder(self.exe, self.root / 'elsewhere'), self.exe.parent)

    def test_initial_picker_uses_settings_default_and_cancel_creates_nothing(self):
        with patch('playlite.lutris_add_dialog.choose_file', return_value=('', '')) as choose:
            self.assertIsNone(choose_executable_entry(None, self.data))
        self.assertEqual(choose.call_args.args[2], str(self.install))
        self.assertEqual(self.count(), 0)
        self.assertFalse(self.plan.prefix.exists())

    def test_dialog_previews_prefix_without_creating_it(self):
        dialog = AddExecutableDialog(str(self.exe), self.data)
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.name.text(), self.folder.name)
        self.assertEqual(dialog.directory.text(), str(self.folder))
        self.assertEqual(dialog.prefix.text(), str(self.plan.prefix))
        dialog.save()
        self.assertIsNotNone(dialog.result_plan)
        self.assertEqual(self.count(), 0)
        self.assertFalse(self.configuration.exists())
        self.assertFalse(self.plan.prefix.exists())

    def test_registration_creates_wine_entry_and_prefix_without_running_exe(self):
        with patch('subprocess.Popen') as spawn:
            with register_executable(self.plan) as action:
                self.assertEqual(action['Integration'], 'LutrisIntegration')
                self.assertEqual(self.count(), 1)
        details = dict(entry_details(self.database, action['GameId']))
        self.assertEqual(details['Executable'], str(self.exe))
        self.assertEqual(details['Wine prefix'], str(self.plan.prefix))
        self.assertEqual(list(self.plan.prefix.iterdir()), [])
        self.assertEqual(self.exe.read_bytes(), b'untouched executable')
        spawn.assert_not_called()
        self.assertEqual(list(self.root.glob('*.bak')), [])

    def test_failed_library_save_rolls_back_entry_files_and_created_parents(self):
        with self.assertRaisesRegex(OSError, 'save failed'):
            with register_executable(self.plan):
                raise OSError('save failed')
        self.assertEqual(self.count(), 0)
        self.assertFalse(self.configuration.exists())
        self.assertFalse(self.plan.prefix.parent.exists())
        with register_executable(self.plan):
            pass
        self.assertEqual(self.count(), 1)

    def test_rollback_preserves_existing_prefix_contents(self):
        self.plan.prefix.mkdir(parents=True)
        existing = self.plan.prefix / 'keep'
        existing.write_text('existing')
        with self.assertRaises(OSError):
            with register_executable(self.plan):
                raise OSError('save failed')
        self.assertEqual(existing.read_text(), 'existing')
        self.assertEqual(self.count(), 0)

    def test_existing_executable_is_not_overwritten(self):
        with register_executable(self.plan):
            pass
        before = list(self.configuration.glob('games/*.yml'))[0].read_bytes()
        with self.assertRaisesRegex(ValueError, 'already'):
            with register_executable(replace(self.plan, name='Changed')):
                pass
        self.assertEqual(self.count(), 1)
        self.assertEqual(list(self.configuration.glob('games/*.yml'))[0].read_bytes(), before)

    def test_pending_action_registers_only_during_save_and_supports_retry(self):
        editor = PlayActionsEditor({'PlayActions': []}, [])
        self.addCleanup(editor.close)
        card = editor.add(dict(Name=self.plan.name, Integration='LutrisIntegration', GameId='', LutrisDatabase=str(self.database)), PendingExecutable(self.plan))
        game = {'PlayActions': editor.collect()}
        self.assertEqual(self.count(), 0)
        self.assertIn('created on Save', card.settings.detail_values['Entry'].text())
        with self.assertRaises(OSError):
            editor.save_with_removals(Mock(side_effect=OSError('save failed')), game)
        self.assertEqual(self.count(), 0)
        self.assertEqual(game['PlayActions'][0]['GameId'], '')
        self.assertIsNotNone(card.pending_installation)
        editor.save_with_removals(lambda: None, game)
        self.assertEqual(self.count(), 1)
        self.assertTrue(card.game_id.text().isdigit())
        self.assertIsNone(card.pending_installation)
        self.assertNotIn('created on Save', card.settings.detail_values['Entry'].text())

    def test_external_changes_are_retained_on_failed_save(self):
        with self.assertRaisesRegex(ValueError, 'retained'):
            with register_executable(self.plan):
                file = list(self.configuration.glob('games/*.yml'))[0]
                file.write_text('game: {exe: changed.exe}\n')
                raise OSError('save failed')
        self.assertEqual(self.count(), 1)
        self.assertIn('changed.exe', file.read_text())

    def test_invalid_executable_is_rejected_before_writes(self):
        with self.assertRaisesRegex(ValueError, 'Windows .exe'):
            with register_executable(replace(self.plan, executable=self.root / 'missing.exe')):
                pass
        self.assertEqual(self.count(), 0)
        self.assertFalse(self.configuration.exists())

    def test_database_insert_failure_removes_staged_config_and_prefix(self):
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("CREATE TRIGGER reject_entry BEFORE INSERT ON games BEGIN SELECT RAISE(ABORT, 'rejected'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            with register_executable(self.plan):
                pass
        self.assertEqual(self.count(), 0)
        self.assertFalse(self.configuration.exists())
        self.assertFalse(self.plan.prefix.parent.exists())

    def test_steam_linked_executable_uses_encoded_id_and_skips_existing_ids(self):
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("INSERT INTO games(id,name,runner) VALUES (4201,'Existing','steam')")
        with register_executable(replace(self.plan, steam_id='42')) as action:
            self.assertEqual(action['GameId'], '4202')
        config = yaml.safe_load(next((self.configuration / 'games').glob('*.yml')).read_text())
        self.assertEqual(config['playlite_steam_id'], 42)

    def test_encoded_ids_reject_invalid_overflow_and_exhausted_ranges(self):
        from playlite.lutris_add import steam_game_id
        with closing(sqlite3.connect(self.database)) as db:
            for value in ('', '0', '-1', 'abc', '４２', str(2**63)):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    steam_game_id(db, value)
            db.executemany('INSERT INTO games(id) VALUES (?)', [(4200+i,) for i in range(1,100)])
            with self.assertRaisesRegex(ValueError, 'in use'):
                steam_game_id(db, '42')

    def test_executable_action_inherits_game_steam_metadata_for_allocation(self):
        from PyQt6.QtWidgets import QWidget
        parent = QWidget()
        parent.data = self.data
        parent.fields = {}
        editor = PlayActionsEditor({'PlayActions': [], 'MetadataIds': {'SteamMetadata': '42'}}, [], parent)
        self.addCleanup(parent.close)
        with patch('playlite.lutris_add_dialog.choose_executable_entry', return_value=replace(self.plan, steam_id='42')) as choose:
            editor.choose_executable()
        self.assertEqual(choose.call_args.kwargs['steam_id'], '42')
        self.assertEqual(editor.cards[0].pending_installation.plan.steam_id, '42')
        game = {'PlayActions': editor.collect()}
        editor.save_with_removals(lambda: None, game)
        self.assertEqual(game['PlayActions'][0]['GameId'], '4201')

    def test_optional_manual_steam_association_keeps_wine_runner(self):
        dialog = AddExecutableDialog(str(self.exe), self.data, steam_id='42')
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.steam_id.text(), '42')
        dialog.steam_id.setText('00084')
        dialog.save()
        self.assertEqual(dialog.result_plan.steam_id, '84')
        with register_executable(dialog.result_plan) as action:
            self.assertEqual(action['GameId'], '8401')
        details = dict(entry_details(self.database, action['GameId']))
        self.assertEqual(details['Runner'], 'Wine')
        self.assertEqual(details['Steam app ID'], '84')
        self.assertEqual(details['Executable'], str(self.exe))

    def test_invalid_manual_steam_id_keeps_dialog_open_without_writes(self):
        dialog = AddExecutableDialog(str(self.exe), self.data)
        self.addCleanup(dialog.close)
        for value in ('abc', '0', '-1', '４２', str(2**63)):
            dialog.steam_id.setText(value)
            dialog.save()
            self.assertIsNone(dialog.result_plan)
            self.assertIn('Steam app ID', dialog.error.text())
        self.assertEqual(self.count(), 0)
        self.assertFalse(self.plan.prefix.exists())

    def test_user_can_change_or_clear_inherited_steam_association(self):
        from PyQt6.QtWidgets import QWidget
        for value in ('84', ''):
            parent = QWidget()
            parent.data = self.data
            parent.fields = {}
            editor = PlayActionsEditor({'PlayActions': [], 'MetadataIds': {'SteamMetadata': '42'}}, [], parent)
            self.addCleanup(parent.close)
            with patch('playlite.lutris_add_dialog.choose_executable_entry', return_value=replace(self.plan, steam_id=value)):
                editor.choose_executable()
            self.assertEqual(editor.cards[0].pending_installation.plan.steam_id, value)

    def test_picker_updates_only_optional_association(self):
        from PyQt6.QtWidgets import QDialog
        dialog = AddExecutableDialog(str(self.exe), self.data)
        self.addCleanup(dialog.close)
        before = (dialog.name.text(), dialog.prefix.text(), dialog.executable.text())
        picker = Mock(selected_game={'id': '84', 'name': 'Another Steam game'})
        with patch('playlite.steam_association.SteamAssociationDialog', return_value=picker), patch('playlite.lutris_add_dialog.run_dialog', return_value=QDialog.DialogCode.Accepted):
            dialog.choose_steam_game()
        self.assertEqual(dialog.steam_id.text(), '84')
        self.assertEqual((dialog.name.text(), dialog.prefix.text(), dialog.executable.text()), before)

    def test_import_preserves_associated_steam_metadata(self):
        from playlite.lutris_library import import_entry
        with register_executable(replace(self.plan, steam_id='42')) as action, patch('playlite.providers.discover_plugins', return_value={}):
            games, _ = import_entry(self.data, [], self.database, action['GameId'], metadata_ids={'SteamMetadata': '42'})
        self.assertEqual(games[0]['MetadataIds'], {'SteamMetadata': '42'})
