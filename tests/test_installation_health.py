from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from playlite.installation_health import check_action, inspect_games
from playlite.app import LibraryWindow


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prefix = self.root / 'prefix'; (self.prefix / 'drive_c').mkdir(parents=True)
        self.exe = self.root / 'game.exe'; self.exe.write_bytes(b'example')
        self.provider = SimpleNamespace(id='LutrisIntegration', action_id_field='LutrisId', launch_configuration=lambda _: {'runner': 'wine', 'game': {'prefix': str(self.prefix), 'exe': str(self.exe)}})
        self.game = {'Id': 'one', 'Name': 'Example'}
        self.action = {'Integration': 'LutrisIntegration', 'GameId': '42', 'Prefix': str(self.prefix), 'Executable': str(self.exe)}

    def test_valid_configuration_is_read_only_and_missing_exe_is_reported(self):
        self.assertFalse(check_action(self.game, self.action, [self.provider])['issues'])
        self.assertEqual(self.exe.read_bytes(), b'example')
        self.exe.unlink()
        self.assertIn('Executable is missing', '\n'.join(check_action(self.game, self.action, [self.provider])['issues']))

    def test_missing_prefix_and_unavailable_integration_are_reported(self):
        (self.prefix / 'drive_c').rmdir(); self.prefix.rmdir()
        self.assertIn('prefix is missing', '\n'.join(check_action(self.game, self.action, [self.provider])['issues']))
        self.assertTrue(check_action(self.game, self.action, [])['issues'])

    def test_vm_and_native_launchers_do_not_require_host_wine_configuration(self):
        vm = dict(self.action, IsVM=True)
        self.assertFalse(check_action(self.game, vm, [])['issues'])
        native = dict(self.action, Prefix='', Executable='/usr/bin/true')
        self.assertFalse(check_action(self.game, native, [self.provider])['issues'])

    def test_incomplete_download_is_reported(self):
        action = dict(self.action, InstallDirectory=str(self.root))
        queue = SimpleNamespace(entries=[SimpleNamespace(destination=str(self.root), state='Paused', name='Example')])
        self.assertIn('Download is not complete', '\n'.join(check_action(self.game, action, [self.provider], queue)['issues']))

    def test_failed_preflight_does_not_launch_or_fire_plugin_hooks(self):
        self.exe.unlink()
        game = dict(self.game, PlayActions=[self.action])
        provider = SimpleNamespace(**vars(self.provider), launch_action=Mock())
        detection = Mock(); detection.status.return_value = 'Stopped'
        plugin = Mock()
        window = SimpleNamespace(current=game, games=[game], game_detection=detection,
            game_providers=[provider], generic_plugins=[plugin], launched_actions={})
        with patch('playlite.app.show_warning') as warning:
            LibraryWindow.play_game(window)
        provider.launch_action.assert_not_called(); plugin.after_launch.assert_not_called()
        self.assertIn('Executable is missing', warning.call_args.args[2])
