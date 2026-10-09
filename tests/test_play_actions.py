from plugin_test_support import require_plugin
require_plugin('LutrisIntegration')
import json
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication, QDialog
from playlite.providers import discover_plugins
from playlite.play_actions import actions_for, action_game, PlayActionsEditor
from playlite.editor import MetadataEditor
from playlite.app import LibraryWindow

APP = QApplication.instance() or QApplication([])


class PlayActionTests(unittest.TestCase):
    def setUp(self):
        self.provider = discover_plugins()['LutrisIntegration']
        self.game = dict(Id='a', Name='Example', GameProvider='LutrisIntegration', LutrisId=42)

    def test_legacy_fallback_explicit_empty_and_integration_override(self):
        self.assertEqual(actions_for(self.game, [self.provider])[0]['Integration'], 'LutrisIntegration')
        self.assertEqual(actions_for(self.game, [self.provider])[0]['Name'], 'Play Example')
        self.assertEqual(actions_for(dict(self.game, PlayActions=[]), [self.provider]), [])
        action = dict(Name='Alternate', Integration='LutrisIntegration', GameId='84')
        configured = dict(self.game, GameProvider=None, PlayActions=[action])
        self.assertEqual(actions_for(configured, [self.provider])[0]['Name'], 'Alternate')
        self.assertTrue(self.provider.owns(configured))
        self.assertEqual(action_game(configured, action, self.provider)['LutrisId'], '84')
        self.assertEqual(configured['LutrisId'], 42)
        with patch.object(self.provider, 'launch') as launch:
            self.provider.launch_action(configured, action)
        self.assertEqual(launch.call_args.args[0]['LutrisId'], '84')

    def test_editor_validation_and_roundtrip(self):
        with TemporaryDirectory() as directory:
            editor = MetadataEditor(self.game, Path(directory))
            editor.play_actions.add(dict(Name='Other', Integration='LutrisIntegration', GameId='84'))
            result = editor.collect()
            self.assertEqual(len(result['PlayActions']), 2)
            self.assertEqual(result['PlayActions'][1]['GameId'], '84')
            editor.play_actions.cards[1].game_id.setText('bad')
            with self.assertRaises(ValueError):
                editor.collect()
            editor.reject()
            actions = PlayActionsEditor(dict(self.game, PlayActions=[]), [self.provider])
            self.assertEqual(actions.collect(), [])

    def test_detection_checks_all_lutris_action_ids(self):
        game = dict(self.game, GameProvider=None, PlayActions=[
            dict(Name='First', Integration='LutrisIntegration', GameId='42'),
            dict(Name='Second', Integration='LutrisIntegration', GameId='84')])
        configs = [dict(LutrisId=42, Executable='/games/first/game'),
                   dict(LutrisId=84, Executable='/games/second/game')]
        process = dict(session='uuid', args=['/games/second/game'], exe='/games/second/game', cwd='/', prefix='')
        import importlib
        detection = importlib.import_module(self.provider.__class__.__module__ + '.detection')
        with patch.object(self.provider, 'import_games', return_value=configs), patch.object(
                detection, 'process_snapshot', return_value=[process]):
            self.assertEqual(self.provider.detect_running([game]), {'a'})

    def test_action_settings_are_independent_and_legacy_fields_migrate(self):
        with TemporaryDirectory() as directory:
            legacy = dict(self.game, Executable='/games/first.exe', Prefix='/prefix/first',
                          LaunchArguments='--old', InstallDirectory='/games/shared')
            editor = MetadataEditor(legacy, Path(directory))
            first = editor.play_actions.cards[0].settings
            self.assertEqual(first.fields['Executable'].text(), '/games/first.exe')
            editor.play_actions.add(dict(Name='Second', Integration='LutrisIntegration', GameId='84', CustomSetting=True))
            second = editor.play_actions.cards[1].settings
            second.fields['Executable'].setText('/other/second.exe')
            second.fields['Prefix'].setText('/prefix/second')
            second.fields['InstallDirectory'].setText('/other')
            first.fields['Arguments'].clear()
            result = editor.collect()
            self.assertNotIn('Executable', result)
            self.assertNotIn('LutrisId', result)
            self.assertEqual(result['InstallDirectory'], '/games/shared')
            self.assertEqual(result['PlayActions'][0]['GameId'], '42')
            configured = action_game(result, result['PlayActions'][0], self.provider)
            self.assertEqual(configured['LaunchArguments'], '')
            self.assertEqual(configured['InstallDirectory'], '/games/shared')
            alternate = action_game(result, result['PlayActions'][1], self.provider)
            self.assertEqual(alternate['InstallDirectory'], '/other')
            self.assertEqual(alternate['Executable'], '/other/second.exe')
            self.assertTrue(result['PlayActions'][1]['CustomSetting'])
            second.fields['Prefix'].setText('relative')
            with self.assertRaises(ValueError):
                editor.collect()
            second.fields['Prefix'].setText('/prefix/second')
            cards = editor.play_actions.cards
            first_card, second_card = cards
            self.assertFalse(first_card.up.isEnabled())
            second_card.up.click()
            self.assertEqual(editor.play_actions.collect()[0]['Name'], 'Second')
            self.assertIs(editor.play_actions.cards[0], second_card)
            second_card.down.click()
            self.assertIs(editor.play_actions.cards[0], first_card)
            self.assertFalse(second_card.down.isEnabled())
            reopened = MetadataEditor(result, Path(directory))
            self.assertEqual(reopened.collect()['PlayActions'], result['PlayActions'])
            reopened.reject()
            editor.reject()

    def test_double_click_and_button_follow_available_play_actions(self):
        with TemporaryDirectory() as directory:
            data = Path(directory)
            game = dict(self.game, PlayActions=[])
            (data / 'library.json').write_text(json.dumps([game]))
            window = LibraryWindow(data)
            item = window.list.item(0)
            window.list.setCurrentItem(item)
            self.assertFalse(window.play_button.isEnabled())
            window.game_status_changed(game['Id'], 'Stopped')
            self.assertFalse(window.play_button.isEnabled())
            with patch.object(window, 'play_game') as launch:
                window.list.itemDoubleClicked.emit(item)
                launch.assert_not_called()
                window.current['PlayActions'] = [dict(Name='Play', Integration='LutrisIntegration', GameId='42')]
                window.game_status_changed(game['Id'], 'Stopped')
                self.assertTrue(window.play_button.isEnabled())
                window.list.itemDoubleClicked.emit(item)
                launch.assert_called_once()
                launch.reset_mock()
                with patch.object(window.game_detection, 'status', return_value='Running'):
                    window.list.itemDoubleClicked.emit(item)
                launch.assert_not_called()
            window.close()

    def test_play_picker_launches_selected_action_and_cancel_does_not_launch(self):
        with TemporaryDirectory() as directory:
            data = Path(directory)
            game = dict(self.game, PlayActions=[dict(Name='First', Integration='LutrisIntegration', GameId='42'),
                                               dict(Name='Second', Integration='LutrisIntegration', GameId='84')])
            (data / 'library.json').write_text(json.dumps([game]))
            window = LibraryWindow(data)
            window.current = game
            provider = next(p for p in window.game_providers if p.id == 'LutrisIntegration')
            def choose(dialog):
                dialog.choose(dialog.method_buttons and game['PlayActions'][1])
                return QDialog.DialogCode.Accepted
            with patch('playlite.app.run_dialog', side_effect=choose), patch.object(provider, 'launch') as launch:
                window.play_game()
                self.assertEqual(launch.call_args.args[0]['LutrisId'], '84')
            window.game_detection.states.clear()
            with patch('playlite.app.run_dialog', return_value=QDialog.DialogCode.Rejected), patch.object(provider, 'launch') as launch:
                window.play_game()
                launch.assert_not_called()
            window.close()
