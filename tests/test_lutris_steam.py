import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import vdf
import yaml
from PyQt6.QtWidgets import QApplication, QDialog
from playlite.steam_library import installed_games
from playlite.lutris_steam import SteamPlan, PendingSteam, register_steam
from playlite.lutris_steam_dialog import AddSteamDialog
from playlite.play_actions import PlayActionsEditor
from playlite.app import LibraryWindow

APP = QApplication.instance() or QApplication([])


class SteamGameTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.steam = self.root / 'Steam'
        self.other = self.root / 'Other library'
        for library in (self.steam, self.other):
            (library / 'steamapps/common').mkdir(parents=True)
        (self.steam / 'steamapps/libraryfolders.vdf').write_text(vdf.dumps({'libraryfolders': {'0': {'path': str(self.steam)}, '1': {'path': str(self.other)}}}))
        self.manifest = self.make_game(self.steam, '42', 'Example', 'Example')
        self.make_game(self.other, '84', 'Second Game', 'Second')
        self.make_game(self.steam, '100', 'Not installed', 'NotInstalled', flags='0')
        self.make_game(self.steam, '101', 'Missing folder', 'Missing', folder=False)
        self.make_game(self.steam, '102', 'Downloading', 'Downloading', flags='1024')
        self.make_game(self.steam, '103', 'Proton Experimental', 'Proton')
        self.make_game(self.steam, '228980', 'Steamworks Shared', 'Steamworks')
        (self.steam / 'steamapps/appmanifest_999.acf').write_text('invalid {')
        patcher = patch('playlite.steam_library.host_environment', return_value={'HOME': str(self.root / 'home'), 'XDG_DATA_HOME': str(self.root)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.database = self.root / 'lutris.db'
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('CREATE TABLE games(id INTEGER PRIMARY KEY, name, sortname, slug, platform, runner, executable, directory, installed, installed_at, configpath, playtime, service, service_id)')
        self.config = self.root / 'lutris-config'
        installation = {'database': self.database, 'flatpak': False, 'config_directory': self.config}
        for module in ('lutris_add', 'lutris_steam_dialog', 'lutris_library'):
            patcher = patch('playlite.'+module+'.installations', return_value=[installation])
            patcher.start()
            self.addCleanup(patcher.stop)
        self.plan = SteamPlan('Example', '42', self.steam / 'steamapps/common/Example', self.manifest, self.database)

    def make_game(self, root, identity, name, directory, flags='4', folder=True):
        manifest = root / 'steamapps' / f'appmanifest_{identity}.acf'
        manifest.write_text(vdf.dumps({'AppState': {'appid': identity, 'name': name, 'installdir': directory, 'StateFlags': flags}}))
        if folder:
            (root / 'steamapps/common' / directory).mkdir(parents=True, exist_ok=True)
        return manifest

    def count(self):
        with closing(sqlite3.connect(self.database)) as db:
            return db.execute('SELECT COUNT(*) FROM games').fetchone()[0]

    def test_only_installed_games_from_all_libraries_are_listed(self):
        self.assertEqual([game['app_id'] for game in installed_games()], ['42', '84'])

    def test_old_libraryfolders_format_and_duplicate_ids_are_supported(self):
        (self.steam / 'steamapps/libraryfolders.vdf').write_text(vdf.dumps({'libraryfolders': {'1': str(self.other)}}))
        self.make_game(self.other, '42', 'Duplicate', 'Duplicate')
        self.assertEqual([game['app_id'] for game in installed_games()], ['42', '84'])

    def test_invalid_paths_and_mismatched_ids_are_not_listed(self):
        self.make_game(self.steam, '104', 'Escape', '../../outside')
        path = self.make_game(self.steam, '105', 'Mismatch', 'Mismatch')
        path.rename(path.with_name('appmanifest_106.acf'))
        self.assertEqual([game['app_id'] for game in installed_games()], ['42', '84'])

    def test_dialog_search_and_selection_do_not_create_entry(self):
        dialog = AddSteamDialog()
        self.addCleanup(dialog.close)
        self.assertEqual(dialog.games.count(), 2)
        dialog.games.setCurrentRow(0)
        self.assertTrue(dialog.add_button.isEnabled())
        dialog.search.setText('does not exist')
        self.assertFalse(dialog.add_button.isEnabled())
        dialog.search.setText('Example')
        dialog.select()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.result_plan.app_id, '42')
        self.assertEqual(self.count(), 0)
        self.assertFalse(self.config.exists())

    def test_registration_uses_steam_runner_and_app_id_without_wine_prefix(self):
        before = self.manifest.read_bytes()
        with register_steam(self.plan) as action:
            self.assertEqual(action['Integration'], 'LutrisIntegration')
        with closing(sqlite3.connect(self.database)) as db:
            row = db.execute('SELECT runner,service_id,executable FROM games').fetchone()
        self.assertEqual(row, ('steam', '42', ''))
        config = yaml.safe_load(next((self.config / 'games').glob('*.yml')).read_text())
        self.assertEqual(config, {'game': {'appid': '42'}, 'playlite_steam_id': 42, 'playlite_id_scheme': 'steam'})
        self.assertEqual(action['GameId'], '4201')
        self.assertEqual(self.manifest.read_bytes(), before)
        self.assertFalse((self.root / 'prefixes').exists())

    def test_uninstalled_selection_is_rechecked_before_registration(self):
        shutil.rmtree(self.plan.directory)
        with self.assertRaisesRegex(ValueError, 'no longer installed'):
            with register_steam(self.plan):
                pass
        self.assertEqual(self.count(), 0)
        self.assertFalse(self.config.exists())

    def test_existing_steam_entry_is_not_duplicated(self):
        with register_steam(self.plan):
            pass
        with self.assertRaisesRegex(ValueError, 'already'):
            with register_steam(self.plan):
                pass
        self.assertEqual(self.count(), 1)

    def test_existing_hand_created_entry_is_detected_from_yaml(self):
        with register_steam(self.plan):
            pass
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE games SET service_id=NULL, service='manual'")
        with self.assertRaisesRegex(ValueError, 'already'):
            with register_steam(self.plan):
                pass
        self.assertEqual(self.count(), 1)

    def test_failed_save_rolls_back_new_entry(self):
        with self.assertRaises(OSError):
            with register_steam(self.plan):
                raise OSError('save failed')
        self.assertEqual(self.count(), 0)
        self.assertFalse(self.config.exists())

    def test_pending_steam_action_shows_app_id_and_registers_on_save(self):
        editor = PlayActionsEditor({'PlayActions': []}, [])
        self.addCleanup(editor.close)
        card = editor.add(dict(Name='Example', Integration='LutrisIntegration', GameId='', LutrisDatabase=str(self.database)), PendingSteam(self.plan))
        self.assertEqual(card.settings.detail_values['Steam app ID'].text(), '42')
        self.assertNotIn('Wine prefix', card.settings.detail_values)
        self.assertEqual(self.count(), 0)
        game = {'PlayActions': editor.collect()}
        editor.save_with_removals(lambda: None, game)
        self.assertEqual(self.count(), 1)
        self.assertTrue(game['PlayActions'][0]['GameId'])
        self.assertEqual(card.settings.detail_values['Steam app ID'].text(), '42')

    def test_main_add_flow_saves_lutris_action_and_steam_metadata_link(self):
        window = SimpleNamespace(settings=Mock(), games=[], data=self.root / 'playlite', focus_added_game=Mock(), statusBar=Mock(return_value=Mock()))
        window.settings.value.return_value = ''
        dialog = Mock(result_plan=self.plan)
        with patch('playlite.lutris_steam_dialog.AddSteamDialog', return_value=dialog), patch('playlite.app.run_dialog', return_value=QDialog.DialogCode.Accepted), patch('playlite.app.save_game', side_effect=lambda data, games, game: [game]):
            LibraryWindow.add_steam_game(window)
        self.assertEqual(window.games[0]['MetadataIds'], {'SteamMetadata': '42'})
        self.assertEqual(window.games[0]['PlayActions'][0]['Integration'], 'LutrisIntegration')
        self.assertEqual(self.count(), 1)

    def test_main_save_failure_rolls_back_lutris_registration(self):
        window = SimpleNamespace(settings=Mock(), games=[], data=self.root / 'playlite')
        window.settings.value.return_value = ''
        with patch('playlite.lutris_steam_dialog.AddSteamDialog', return_value=Mock(result_plan=self.plan)), patch('playlite.app.run_dialog', return_value=QDialog.DialogCode.Accepted), patch('playlite.app.save_game', side_effect=OSError('save failed')), patch('playlite.app.show_warning') as warning:
            LibraryWindow.add_steam_game(window)
        warning.assert_called_once()
        self.assertEqual(self.count(), 0)
        self.assertFalse(self.config.exists())
        self.assertEqual(window.games, [])

    def test_flatpak_steam_libraries_are_detected(self):
        root = self.root / 'home/.var/app/com.valvesoftware.Steam/data/Steam'
        (root / 'steamapps/common').mkdir(parents=True)
        self.make_game(root, '126', 'Flatpak Game', 'Flatpak')
        self.assertEqual({game['app_id'] for game in installed_games()}, {'42', '84', '126'})

    def test_installed_game_in_symlinked_folder_is_listed(self):
        target=self.root/'relocated-game';target.mkdir()
        self.make_game(self.steam,'127','Relocated game','Relocated',folder=False)
        (self.steam/'steamapps/common/Relocated').symlink_to(target,target_is_directory=True)
        self.assertIn('127',{game['app_id'] for game in installed_games()})
