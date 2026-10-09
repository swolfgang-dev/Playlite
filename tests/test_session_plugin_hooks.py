from types import SimpleNamespace
import unittest
from unittest.mock import Mock
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

    def test_exit_hook_receives_launched_action_once(self):
        plugin = Mock()
        action = {'Integration': 'Example', 'GameId': '42'}
        window = SimpleNamespace(launched_actions={'one': action}, games=[self.game], generic_plugins=[plugin])
        LibraryWindow.game_session_finished(window, 'one')
        plugin.after_game_stopped.assert_called_once_with(window, self.game, action)
        self.assertNotIn('one', window.launched_actions)

    def test_launch_hook_receives_chosen_action(self):
        action = {'Name': 'Example', 'Integration': 'Example', 'GameId': '42'}
        game = dict(self.game, PlayActions=[action])
        plugin = Mock(); plugin.before_launch.return_value = True
        provider = self.provider; provider.launch_action = Mock()
        detection = Mock(); detection.status.return_value = 'Stopped'
        window = SimpleNamespace(current=game, games=[game], game_detection=detection,
            game_providers=[provider], generic_plugins=[plugin], launched_actions={})
        LibraryWindow.play_game(window)
        plugin.after_launch.assert_called_once()
        self.assertEqual(plugin.after_launch.call_args.args[2]['GameId'], '42')
        self.assertEqual(window.launched_actions['one']['GameId'], '42')
