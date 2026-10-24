from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from PyQt6.QtCore import QCoreApplication
from playlite.game_detection import GameDetection
from playlite.providers import IntegrationPlugin
from playlite.app import LibraryWindow

APP = QCoreApplication.instance() or QCoreApplication([])


class Integration(IntegrationPlugin):
    id = 'Example'
    name = 'Example'


class SessionHookTests(unittest.TestCase):
    def setUp(self):
        self.game = dict(Id='one', Name='Example', GameProvider='Example')
        self.provider = Integration()
        self.detection = GameDetection([self.provider], lambda: [self.game], recorder=lambda *args: True)
        self.finished = Mock(); self.detection.session_finished.connect(self.finished)

    def test_finished_only_after_confirmed_exit(self):
        self.detection.observe({'Example': ([self.game], {'one'})}, now=0)
        self.detection.observe({'Example': ([self.game], set())}, now=10)
        self.finished.assert_not_called()
        self.detection.observe({'Example': ([self.game], set())}, now=13)
        self.finished.assert_called_once_with('one')
        self.detection.observe({'Example': ([self.game], set())}, now=15)
        self.finished.assert_called_once_with('one')

    def test_closing_playlite_does_not_report_game_exit(self):
        self.detection.observe({'Example': ([self.game], {'one'})}, now=0)
        self.detection.stop()
        self.finished.assert_not_called()

    def test_failed_exit_checkpoint_retries_at_original_stop_time(self):
        recorder = Mock(side_effect=[True, False, True])
        self.detection.recorder = recorder
        self.detection.observe({'Example': ([self.game], {'one'})}, now=0)
        for now in (10, 13, 15):
            self.detection.observe({'Example': ([self.game], set())}, now=now)
        self.assertEqual([call.args[1:3] for call in recorder.call_args_list],
                         [(0, 1), (10, 0), (10, 0)])
        self.finished.assert_called_once_with('one')

    def test_multiple_integrations_reach_one_combined_decision(self):
        other = Integration()
        other.id = 'Other'
        self.detection.integrations.append(other)
        self.game['PlayActions'] = [{'Integration': 'Example'}, {'Integration': 'Other'}]
        for now in (0, 10, 13):
            self.detection.observe({'Example': ([self.game], {'one'}),
                                    'Other': ([self.game], set())}, now=now)
        self.assertEqual(self.detection.status('one'), 'Running')
        self.finished.assert_not_called()
        # A missing detector result is uncertainty rather than a confirmed stop.
        for now in (20, 23):
            self.detection.observe({'Other': ([self.game], set())}, now=now)
        self.assertEqual(self.detection.status('one'), 'Running')
        for now in (30, 33):
            self.detection.observe({'Example': ([self.game], set()),
                                    'Other': ([self.game], set())}, now=now)
        self.finished.assert_called_once_with('one')

    def test_exit_hook_receives_launched_action_once(self):
        plugin = Mock()
        action = {'Integration': 'Example', 'GameId': '42'}
        window = SimpleNamespace(launched_actions={'one': action}, games=[self.game], generic_plugins=[plugin])
        LibraryWindow.game_session_finished(window, 'one')
        plugin.after_game_stopped.assert_called_once_with(window, self.game, action)
        self.assertNotIn('one', window.launched_actions)

    def test_launch_hook_receives_chosen_action(self):
        action = {'Name': 'Example', 'Integration': 'LutrisIntegration', 'GameId': '42', 'LutrisDatabase': '/fixture/pga.db'}
        game = dict(self.game, PlayActions=[action])
        plugin = Mock(); plugin.before_launch.return_value = True
        provider = self.provider; provider.launch_action = Mock()
        detection = Mock(); detection.status.return_value = 'Stopped'
        window = SimpleNamespace(current=game, games=[game], game_detection=detection,
            game_providers=[provider], generic_plugins=[plugin], launched_actions={}, statusBar=Mock())
        with patch('playlite.installation_health.check_action', return_value={'issues': []}), \
             patch('playlite.lutris_launch.launch_action') as launch:
            LibraryWindow.play_game(window)
        launch.assert_called_once()
        plugin.before_action_launch.assert_called_once_with(window, game, launch.call_args.args[0])
        plugin.after_launch.assert_called_once()
        self.assertEqual(plugin.after_launch.call_args.args[2]['GameId'], '42')
        self.assertEqual(window.launched_actions['one']['GameId'], '42')

    def test_cancelled_action_preflight_prevents_launch(self):
        action = {'Name': 'Example', 'Integration': 'LutrisIntegration', 'GameId': '42', 'LutrisDatabase': '/fixture/pga.db'}
        game = dict(self.game, PlayActions=[action])
        plugin = Mock(); plugin.before_launch.return_value = True
        plugin.before_action_launch.return_value = False
        provider = self.provider; provider.launch_action = Mock()
        detection = Mock(); detection.status.return_value = 'Stopped'
        window = SimpleNamespace(current=game, games=[game], game_detection=detection,
            game_providers=[provider], generic_plugins=[plugin], launched_actions={}, statusBar=Mock())
        with patch('playlite.installation_health.check_action', return_value={'issues': []}), \
             patch('playlite.lutris_launch.launch_action') as launch:
            LibraryWindow.play_game(window)
        launch.assert_not_called()
        provider.launch_action.assert_not_called()
        plugin.after_launch.assert_not_called()
