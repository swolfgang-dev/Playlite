import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from playlite.lutris_requirement import require_lutris, validate_lutris_association

APP = QApplication.instance() or QApplication([])


class LutrisRequirementTests(unittest.TestCase):
    def test_native_lutris_is_sufficient(self):
        with patch('playlite.lutris_requirement.shutil.which', return_value='/usr/games/lutris'), patch('playlite.lutris_requirement.subprocess.run') as run:
            require_lutris()
        run.assert_not_called()

    def test_flatpak_lutris_must_be_installed(self):
        with patch('playlite.lutris_requirement.shutil.which', side_effect=[None, '/usr/bin/flatpak']), patch('playlite.lutris_requirement.subprocess.run', return_value=SimpleNamespace(returncode=0)) as run:
            require_lutris()
        self.assertEqual(run.call_args.args[0], ['/usr/bin/flatpak', 'info', 'net.lutris.Lutris'])
        with patch('playlite.lutris_requirement.shutil.which', return_value=None), self.assertRaisesRegex(ValueError, 'requires Lutris'):
            require_lutris()

    def test_every_action_requires_lutris(self):
        good = {'Integration': 'LutrisIntegration', 'GameId': '42'}
        validate_lutris_association({'PlayActions': [good]})
        validate_lutris_association({'LutrisId': 42})
        for game in ({}, {'PlayActions': []}, {'PlayActions': [good, {'Integration': 'Manual'}]}, {'GameProvider': 'SteamIntegration', 'LutrisId': 42}):
            with self.subTest(game=game), self.assertRaises(ValueError):
                validate_lutris_association(game)
        for identity in ('', '0', '-1', '４２', 'abc'):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                validate_lutris_association({'PlayActions': [dict(good, GameId=identity)]})

    def test_manual_is_not_discovered_or_offered(self):
        from playlite.providers import discover_plugins, installation_methods
        with TemporaryDirectory() as directory:
            self.assertEqual(discover_plugins(Path(directory)), {})
        self.assertEqual(installation_methods({}), {})

    def test_unavailable_integration_has_clear_add_error(self):
        from playlite.add_game import AddGameEditor
        with TemporaryDirectory() as directory, patch('playlite.providers.discover_plugins', return_value={}):
            with self.assertRaisesRegex(ValueError, 'Lutris integration'):
                AddGameEditor('', Path(directory))

    def test_unlinked_save_fails_before_creating_files(self):
        from playlite.game_storage import save_game
        with TemporaryDirectory() as directory:
            data = Path(directory) / 'library'
            with self.assertRaisesRegex(ValueError, 'Lutris entry'):
                save_game(data, [], {'Id': 'example', 'Name': 'Example'})
            self.assertFalse(data.exists())
