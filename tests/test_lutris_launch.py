import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PyQt6.QtWidgets import QApplication, QDialog
from playlite.lutris_launch import launch_action, resolve_action
from playlite.lutris_library import installations
from playlite.play_actions import PlayActionsEditor, actions_for
from playlite.app import LibraryWindow
from playlite.installation_health import check_action

APP = QApplication.instance() or QApplication([])


class LutrisLaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / 'pga.db'
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('CREATE TABLE games(id INTEGER PRIMARY KEY, name TEXT, installed INTEGER)')
            db.executemany('INSERT INTO games VALUES (?, ?, 1)', [(42, 'Example'), (84, 'Alternate')])
        self.installation = {'database': self.database, 'flatpak': False}
        self.action = {'Name': 'Play', 'Integration': 'LutrisIntegration', 'GameId': '42', 'LutrisDatabase': str(self.database)}
        patcher = patch('playlite.lutris_launch.installations', return_value=[self.installation])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.environment = {'HOME': str(self.root), 'PATH': '/usr/bin', 'DISPLAY': ':1'}
        patcher = patch('playlite.lutris_launch.host_environment', return_value=self.environment)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_native_launch_passes_only_selected_id_and_host_environment(self):
        action = dict(self.action, Executable='/missing/stale.exe', Prefix='/missing/prefix', Arguments='--stale', InstallDirectory='/missing')
        with patch('playlite.lutris_launch.shutil.which', return_value='/usr/games/lutris'), patch('playlite.lutris_launch.subprocess.Popen') as spawn:
            launch_action(action)
        spawn.assert_called_once_with(['/usr/games/lutris', 'lutris:rungameid/42'], env=self.environment, start_new_session=True)
        self.assertFalse(check_action({}, action, [])['issues'])

    def test_flatpak_launch_uses_matching_lutris(self):
        self.installation['flatpak'] = True
        with patch('playlite.lutris_launch.shutil.which', return_value='/usr/bin/flatpak'), patch('playlite.lutris_launch.subprocess.run', return_value=SimpleNamespace(returncode=0)), patch('playlite.lutris_launch.subprocess.Popen') as spawn:
            launch_action(self.action)
        spawn.assert_called_once_with(['/usr/bin/flatpak', 'run', 'net.lutris.Lutris', 'lutris:rungameid/42'], env=self.environment, start_new_session=True)

    def test_deleted_entry_or_unknown_database_never_launches(self):
        with patch('playlite.lutris_launch.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(ValueError, 'no longer exists'):
                launch_action(dict(self.action, GameId='999'))
            with self.assertRaisesRegex(ValueError, 'active library'):
                launch_action(dict(self.action, LutrisDatabase=str(self.root / 'other.db')))
        spawn.assert_not_called()

    def test_missing_runtime_never_launches(self):
        with patch('playlite.lutris_launch.shutil.which', return_value=None), patch('playlite.lutris_launch.subprocess.Popen') as spawn:
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                launch_action(self.action)
        spawn.assert_not_called()

    def test_legacy_action_requires_unambiguous_library(self):
        legacy = dict(self.action)
        legacy.pop('LutrisDatabase')
        self.assertEqual(resolve_action(legacy)[1]['id'], '42')
        with patch('playlite.lutris_launch.installations', return_value=[self.installation, dict(self.installation, flatpak=True)]):
            with self.assertRaisesRegex(ValueError, 'library'):
                resolve_action(legacy)

    def test_configured_lutris_database_is_recognized(self):
        config = self.root / 'config/lutris'
        config.mkdir(parents=True)
        (config / 'lutris.conf').write_text('[lutris]\npga_path = '+str(self.database)+'\n')
        with patch('playlite.lutris_library.host_environment', return_value={'HOME': str(self.root), 'XDG_CONFIG_HOME': str(config.parent)}):
            self.assertEqual(installations()[0]['database'], self.database)

    def window(self, actions):
        game = {'Id': 'example', 'Name': 'Example', 'PlayActions': actions}
        window = SimpleNamespace(current=game, games=[game], game_providers=[], generic_plugins=[],
                                 automation=None, launched_actions={}, game_detection=Mock(), statusBar=Mock(return_value=Mock()))
        window.game_detection.status.return_value = 'Stopped'
        return window

    def test_play_button_launches_default_without_provider_plugin(self):
        alternate = dict(self.action, GameId='84', Name='Alternate', Default=True)
        window = self.window([self.action, alternate])
        self.assertTrue(LibraryWindow.has_play_actions(window, window.current))
        with patch('playlite.lutris_launch.launch_action') as launch, patch('playlite.app.show_warning') as warning:
            LibraryWindow.play_game(window)
        launch.assert_called_once_with(alternate)
        warning.assert_not_called()
        self.assertEqual(window.launched_actions['example']['GameId'], '84')

    def test_action_chooser_launches_chosen_entry(self):
        alternate = dict(self.action, GameId='84', Name='Alternate')
        window = self.window([self.action, alternate])
        picker = Mock(selected_method=alternate)
        with patch('playlite.add_game.AddGameMethods', return_value=picker), patch('playlite.app.run_dialog', return_value=QDialog.DialogCode.Accepted), patch('playlite.lutris_launch.launch_action') as launch:
            LibraryWindow.play_game(window)
        launch.assert_called_once_with(alternate)

    def test_cancelled_before_launch_hook_does_not_dispatch(self):
        window = self.window([self.action])
        window.generic_plugins = [Mock(before_launch=Mock(return_value=False))]
        with patch('playlite.lutris_launch.launch_action') as launch:
            LibraryWindow.play_game(window)
        launch.assert_not_called()

    def test_action_editor_keeps_identity_and_removes_stale_overrides(self):
        action = dict(self.action, Executable='/stale.exe', Prefix='/stale', Arguments='--stale')
        editor = PlayActionsEditor({'PlayActions': [action]}, [])
        self.addCleanup(editor.close)
        collected = editor.collect()[0]
        self.assertEqual(collected['GameId'], '42')
        self.assertEqual(collected['LutrisDatabase'], str(self.database))
        self.assertNotIn('Executable', collected)
        self.assertNotIn('Prefix', collected)
        self.assertNotIn('Arguments', collected)
        self.assertEqual(editor.cards[0].integration.currentText(), 'Lutris')

    def test_legacy_game_gets_core_action_without_plugin_discovery(self):
        actions = actions_for({'Name': 'Example', 'LutrisId': 42}, [])
        self.assertEqual(actions[0]['Integration'], 'LutrisIntegration')
        self.assertEqual(actions[0]['GameId'], '42')

    def test_add_action_selects_existing_lutris_entry(self):
        editor = PlayActionsEditor({'PlayActions': [self.action]}, [])
        self.addCleanup(editor.close)
        picker = Mock(selected_entry={'id': '84', 'name': 'Alternate', 'database': str(self.database)})
        with patch('playlite.lutris_import.LutrisImportDialog', return_value=picker), patch('playlite.lifecycle.run_dialog', return_value=QDialog.DialogCode.Accepted):
            editor.choose_action()
        self.assertEqual([action['GameId'] for action in editor.collect()], ['42', '84'])

    def test_action_can_be_relinked_to_different_entry(self):
        editor = PlayActionsEditor({'PlayActions': [self.action]}, [])
        self.addCleanup(editor.close)
        picker = Mock(selected_entry={'id': '84', 'name': 'Alternate', 'database': str(self.database)})
        with patch('playlite.lutris_import.LutrisImportDialog', return_value=picker), patch('playlite.lifecycle.run_dialog', return_value=QDialog.DialogCode.Accepted):
            editor.cards[0].settings.choose_entry()
        self.assertEqual(editor.collect()[0]['GameId'], '84')

    def test_dispatch_failure_is_reported_without_success_hooks(self):
        window = self.window([self.action])
        plugin = Mock(before_launch=Mock(return_value=True), before_action_launch=Mock(return_value=True))
        window.generic_plugins = [plugin]
        with patch('playlite.lutris_launch.launch_action', side_effect=OSError('Lutris unavailable')), patch('playlite.app.show_warning') as warning:
            LibraryWindow.play_game(window)
        warning.assert_called_once()
        plugin.after_launch.assert_not_called()
        self.assertEqual(window.launched_actions, {})

    def test_before_launch_automation_completes_before_dispatch(self):
        window = self.window([self.action])
        window.automation = Mock()
        window.automation.busy.return_value = False
        events = []
        def automate(game, action, phase, completed):
            events.append(phase)
            completed()
        window.automation.run.side_effect = automate
        with patch('playlite.lutris_launch.launch_action', side_effect=lambda action: events.append('launch')):
            LibraryWindow.play_game(window)
        self.assertEqual(events, ['before_launch', 'launch'])
        window.automation.launched.assert_called_once()
