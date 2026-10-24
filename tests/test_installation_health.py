"""Health checks resolve Lutris associations without owning runner settings."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from playlite.installation_health import check_action, inspect_games
from playlite.app import LibraryWindow


class HealthTests(unittest.TestCase):
    def test_resolves_live_lutris_entry_and_leaves_runner_checks_to_lutris(self):
        action = dict(Integration='LutrisIntegration', GameId='42', LutrisDatabase='/fixture/pga.db')
        with patch('playlite.lutris_launch.resolve_action', return_value=(None, {'name': 'Example'})) as resolve:
            result = check_action({}, action, [])
        resolve.assert_called_once_with(action)
        self.assertEqual(result['issues'], [])
        self.assertIn('Lutris manages', result['checked'][1])

    def test_missing_entry_is_reported_and_empty_actions_need_attention(self):
        with patch('playlite.lutris_launch.resolve_action', side_effect=ValueError('Entry no longer exists')):
            self.assertEqual(check_action({}, {}, [])['issues'], ['Entry no longer exists'])
        self.assertIn('No play actions', inspect_games([{'Name': 'Example', 'PlayActions': []}], [])[0]['issues'][0])

    def test_failed_preflight_prevents_launcher_and_plugin_hooks(self):
        game = dict(Id='one', Name='Example', PlayActions=[dict(Integration='LutrisIntegration', GameId='42')])
        detection = Mock(); detection.status.return_value = 'Stopped'
        plugin = Mock()
        window = SimpleNamespace(current=game, games=[game], game_detection=detection,
            game_providers=[], generic_plugins=[plugin], launched_actions={})
        with patch('playlite.lutris_launch.resolve_action', side_effect=ValueError('Entry no longer exists')), \
             patch('playlite.lutris_launch.launch_action') as launch, patch('playlite.app.show_warning') as warning:
            LibraryWindow.play_game(window)
        launch.assert_not_called(); plugin.before_launch.assert_not_called(); plugin.after_launch.assert_not_called()
        self.assertIn('Entry no longer exists', warning.call_args.args[2])
